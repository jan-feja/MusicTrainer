"""Detects chords in the background, one song at a time (a few seconds each).

Chords sit on the beat grid, and each user can have their own grid (their
fixes), so chords are detected and kept per grid. Once stems exist, they are
detected again on the pitched stems.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from music_trainer.models import AnalysisStatus, BeatAnalysis, ChordAnalysis, ChordDetectionState
from music_trainer.services.audio import AudioDecodeError
from music_trainer.services.chords import (
    HARMONIC_STEMS,
    ChordDetectionError,
    ChordDetector,
    beat_grid_key,
)
from music_trainer.services.library import Library, VideoNotInLibraryError
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    video_id: str
    grid: str
    beats: list[float]
    status: AnalysisStatus = AnalysisStatus.QUEUED
    error: str | None = None


class ChordDetectionManager:
    """Starts chord detection and reports its state; results go to the Library."""

    def __init__(self, detector: ChordDetector, library: Library) -> None:
        self._detector = detector
        self._library = library
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chords")
        self._jobs: dict[tuple[str, str], _Job] = {}  # by video and grid
        self._lock = threading.Lock()

    def start(self, video_id: str, beats: BeatAnalysis, force: bool = False) -> ChordDetectionState:
        """Detect the chords on the beat grid `beats` unless that is running or done."""
        self._require_video(video_id)
        grid = beat_grid_key(beats)
        with self._lock:
            job = self._jobs.get((video_id, grid))
            if job is not None and job.status.is_active:
                return self._state_of(job)
            current = None if force else self._current_chords(video_id, grid)
            if current is not None:
                return self._completed(video_id, current)
            job = _Job(video_id, grid=grid, beats=list(beats.beats))
            self._jobs[(video_id, grid)] = job
            self._executor.submit(self._run, job)
            return self._state_of(job)

    def get_state(self, video_id: str, grid: str) -> ChordDetectionState:
        """The chords on the beat grid with the key `grid` (see chords.beat_grid_key)."""
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get((video_id, grid))
            if job is not None and job.status is not AnalysisStatus.COMPLETED:
                return self._state_of(job)
        current = self._current_chords(video_id, grid)
        if current is not None:
            return self._completed(video_id, current)
        return ChordDetectionState(video_id=video_id, grid=grid, status=AnalysisStatus.NOT_STARTED)

    def forget(self, video_id: str) -> None:
        """Drop the finished jobs of a video, e.g. after it was deleted."""
        with self._lock:
            for key in [k for k, job in self._jobs.items() if k[0] == video_id]:
                if not self._jobs[key].status.is_active:
                    del self._jobs[key]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: _Job) -> None:
        self._update(job, status=AnalysisStatus.ANALYZING)
        try:
            media_path = self._library.media_path(job.video_id)
            if media_path is None:
                raise VideoNotInLibraryError(job.video_id)
            stems = self._library.stem_paths(job.video_id, HARMONIC_STEMS)
            chords = self._detector.detect(media_path, stems, job.beats)
            analysis = ChordAnalysis(
                method=self._detector.method,
                chords=chords,
                grid=job.grid,
                from_stems=bool(stems),
            )
            self._library.write_chords(job.video_id, analysis)
        except (ChordDetectionError, AudioDecodeError, VideoNotInLibraryError) as error:
            logger.warning("Chord detection of %s failed: %s", job.video_id, error)
            self._update(job, status=AnalysisStatus.FAILED, error=str(error))
        except Exception:
            logger.exception("Chord detection of %s failed unexpectedly", job.video_id)
            self._update(
                job,
                status=AnalysisStatus.FAILED,
                error="Unexpected error during chord detection; see the server log.",
            )
        else:
            logger.info("Chords of %s: %d", job.video_id, len(chords))
            self._update(job, status=AnalysisStatus.COMPLETED)

    def _current_chords(self, video_id: str, grid: str) -> ChordAnalysis | None:
        """The stored chords on the grid, unless made without the stems that are there now."""
        chords = self._library.read_chords(video_id, grid)
        if chords is None:
            return None
        if not chords.from_stems and self._library.read_stems(video_id) is not None:
            return None
        return chords

    @staticmethod
    def _completed(video_id: str, chords: ChordAnalysis) -> ChordDetectionState:
        return ChordDetectionState(
            video_id=video_id, grid=chords.grid, status=AnalysisStatus.COMPLETED, analysis=chords
        )

    def _require_video(self, video_id: str) -> None:
        if not self._library.contains(require_valid_video_id(video_id)):
            raise VideoNotInLibraryError(video_id)

    @staticmethod
    def _state_of(job: _Job) -> ChordDetectionState:
        return ChordDetectionState(
            video_id=job.video_id, grid=job.grid, status=job.status, error=job.error
        )

    def _update(self, job: _Job, **changes: object) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(job, name, value)
