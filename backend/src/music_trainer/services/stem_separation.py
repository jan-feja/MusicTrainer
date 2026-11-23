"""Separates songs into stems in the background, one song at a time (it uses all CPU cores).

A job separates into the video's stems.partial/ folder, which replaces stems/
when complete, so the player never sees half a set. New downloads join the end
of the queue; the song open in the player goes to its front.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from music_trainer.models import AnalysisStatus, StemSeparationState
from music_trainer.services.audio import AudioDecodeError
from music_trainer.services.library import Library, VideoNotInLibraryError
from music_trainer.services.stems import StemSeparationError, StemSeparator
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    video_id: str
    status: AnalysisStatus = AnalysisStatus.QUEUED
    progress: float | None = None
    error: str | None = None
    cancelled: bool = False


class StemSeparationManager:
    """Starts stem separation and reports its state; results go to the Library."""

    def __init__(self, separator: StemSeparator, library: Library) -> None:
        self._separator = separator
        self._library = library
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stems")
        self._jobs: dict[str, _Job] = {}
        self._queue: list[_Job] = []
        """Queued jobs, the next one first."""
        self._running: _Job | None = None
        self._lock = threading.Lock()

    def start(self, video_id: str, force: bool = False, first: bool = False) -> StemSeparationState:
        """Separate the video unless that is running or done; `force` separates again.

        `first` puts it at the front of the queue (or moves it there if queued).
        """
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status.is_active:
                if first and job in self._queue:
                    self._queue.remove(job)
                    self._queue.insert(0, job)
                return self._state_of(job)
            if not force:
                stems = self._library.read_stems(video_id)
                if stems is not None:
                    return StemSeparationState(
                        video_id=video_id, status=AnalysisStatus.COMPLETED, stems=stems
                    )
            job = _Job(video_id)
            self._jobs[video_id] = job
            if first:
                self._queue.insert(0, job)
            else:
                self._queue.append(job)
            # each task runs whichever job is first in the queue then
            self._executor.submit(self._run_next)
            return self._state_of(job)

    def get_state(self, video_id: str) -> StemSeparationState:
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status is not AnalysisStatus.COMPLETED:
                return self._state_of(job)
        stems = self._library.read_stems(video_id)
        if stems is not None:
            return StemSeparationState(
                video_id=video_id, status=AnalysisStatus.COMPLETED, stems=stems
            )
        return StemSeparationState(video_id=video_id, status=AnalysisStatus.NOT_STARTED)

    def forget(self, video_id: str) -> None:
        """Drop the video's job, stopping it if it runs, e.g. after the video was deleted."""
        with self._lock:
            job = self._jobs.pop(video_id, None)
            if job is None:
                return
            job.cancelled = True
            if job in self._queue:
                self._queue.remove(job)
            running = job is self._running
        if running:
            self._separator.stop()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._separator.stop()

    def _run_next(self) -> None:
        with self._lock:
            if not self._queue:  # its job was dropped
                return
            job = self._queue.pop(0)
            self._running = job
            job.status = AnalysisStatus.ANALYZING
            job.progress = 0.0
        try:
            media_path = self._library.media_path(job.video_id)
            if media_path is None:
                raise VideoNotInLibraryError(job.video_id)
            out_dir = self._library.create_stems_staging_dir(job.video_id)
            stems = self._separator.separate(
                media_path, out_dir, lambda progress: self._update(job, progress=progress)
            )
            with self._lock:
                if job.cancelled:
                    return
            self._library.commit_stems(job.video_id, stems)
        except (StemSeparationError, AudioDecodeError, VideoNotInLibraryError, OSError) as error:
            self._fail(job, str(error))
        except Exception:
            logger.exception("Stem separation of %s failed unexpectedly", job.video_id)
            self._fail(job, "Unexpected error during stem separation; see the server log.")
        else:
            logger.info("Stems of %s: %s", job.video_id, ", ".join(s.name for s in stems.stems))
            self._update(job, status=AnalysisStatus.COMPLETED, progress=1.0)
        finally:
            with self._lock:
                self._running = None

    def _fail(self, job: _Job, error: str) -> None:
        if not job.cancelled:
            logger.warning("Stem separation of %s failed: %s", job.video_id, error)
            self._library.discard_stems_staging(job.video_id)
        self._update(job, status=AnalysisStatus.FAILED, error=error)

    def _require_video(self, video_id: str) -> None:
        if not self._library.contains(require_valid_video_id(video_id)):
            raise VideoNotInLibraryError(video_id)

    def _state_of(self, job: _Job) -> StemSeparationState:
        """Call with the lock held."""
        position = None
        if job in self._queue:
            position = self._queue.index(job) + (1 if self._running is not None else 0)
        return StemSeparationState(
            video_id=job.video_id,
            status=job.status,
            progress=job.progress,
            queue_position=position,
            error=job.error,
        )

    def _update(self, job: _Job, **changes: object) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(job, name, value)
