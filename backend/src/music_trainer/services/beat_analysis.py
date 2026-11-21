"""Runs beat detection in the background, one song at a time (it uses all CPU cores)."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from music_trainer.models import AnalysisStatus, BeatTrackingState
from music_trainer.services.audio import AudioDecodeError
from music_trainer.services.beats import BeatTracker, BeatTrackingError
from music_trainer.services.library import Library, VideoNotInLibraryError
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    video_id: str
    status: AnalysisStatus = AnalysisStatus.QUEUED
    error: str | None = None


class BeatAnalysisManager:
    """Starts beat detection and reports its state; results go to the Library."""

    def __init__(self, tracker: BeatTracker, library: Library) -> None:
        self._tracker = tracker
        self._library = library
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="beats")
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    def start(self, video_id: str, force: bool = False) -> BeatTrackingState:
        """Detect the beats unless that is running or done (`force` redoes finished work)."""
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status.is_active:
                return self._state_of(job)
            if not force and (analysis := self._library.read_beat_analysis(video_id)):
                return BeatTrackingState(
                    video_id=video_id, status=AnalysisStatus.COMPLETED, analysis=analysis
                )
            job = _Job(video_id)
            self._jobs[video_id] = job
            self._executor.submit(self._run, job)
            return self._state_of(job)

    def get_state(self, video_id: str) -> BeatTrackingState:
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status is not AnalysisStatus.COMPLETED:
                return self._state_of(job)
        analysis = self._library.read_beat_analysis(video_id)
        if analysis is not None:
            return BeatTrackingState(
                video_id=video_id, status=AnalysisStatus.COMPLETED, analysis=analysis
            )
        return BeatTrackingState(video_id=video_id, status=AnalysisStatus.NOT_STARTED)

    def forget(self, video_id: str) -> None:
        """Drop a finished job, e.g. after its video was deleted."""
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and not job.status.is_active:
                del self._jobs[video_id]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: _Job) -> None:
        self._update(job, status=AnalysisStatus.ANALYZING)
        media_path = self._library.media_path(job.video_id)
        try:
            if media_path is None:
                raise VideoNotInLibraryError(job.video_id)
            analysis = self._tracker.analyze(media_path)
            self._library.write_beat_analysis(job.video_id, analysis)
        except (BeatTrackingError, AudioDecodeError, VideoNotInLibraryError) as error:
            logger.warning("Beat detection of %s failed: %s", job.video_id, error)
            self._update(job, status=AnalysisStatus.FAILED, error=str(error))
        except Exception:
            logger.exception("Beat detection of %s failed unexpectedly", job.video_id)
            self._update(
                job,
                status=AnalysisStatus.FAILED,
                error="Unexpected error during beat detection; see the server log.",
            )
        else:
            logger.info(
                "Beats of %s: %d beats, %s BPM", job.video_id, len(analysis.beats), analysis.bpm
            )
            self._update(job, status=AnalysisStatus.COMPLETED)

    def _require_video(self, video_id: str) -> None:
        if not self._library.contains(require_valid_video_id(video_id)):
            raise VideoNotInLibraryError(video_id)

    @staticmethod
    def _state_of(job: _Job) -> BeatTrackingState:
        return BeatTrackingState(video_id=job.video_id, status=job.status, error=job.error)

    def _update(self, job: _Job, **changes: object) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(job, name, value)
