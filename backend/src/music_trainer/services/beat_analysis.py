"""Runs beat detection in the background, one song at a time (it uses all CPU cores).

A job runs the beat network (or reuses its stored output) and decodes the
detected grid, which everyone who has the song shares. A user's fixes (hints)
give that user's own grid: the stored network output is decoded again with
them, which takes a moment. The last decodings are kept in memory, so moving
the bar starts is instant.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from music_trainer.models import AnalysisStatus, BeatAnalysis, BeatGridHints, BeatTrackingState
from music_trainer.services.audio import AudioDecodeError
from music_trainer.services.beat_decoding import DecodedBeats
from music_trainer.services.beats import (
    GRID_DECODER,
    NO_HINTS,
    BeatTracker,
    BeatTrackingError,
    decode_grid,
    grid_analysis,
    is_current_analysis,
)
from music_trainer.services.library import Library, VideoNotInLibraryError
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)

_DECODINGS_KEPT = 16
_DecodingKey = tuple[str, str, int | None, float | None]  # video, model, beats per bar, tempo


class BeatsNotDetectedError(Exception):
    def __init__(self, video_id: str) -> None:
        super().__init__(f"The beats of {video_id} are not detected yet")


@dataclass
class _Job:
    video_id: str
    rerun_network: bool
    """Run the network even if its output is stored."""
    status: AnalysisStatus = AnalysisStatus.QUEUED
    error: str | None = None


class BeatAnalysisManager:
    """Starts beat detection and reports its state; results go to the Library."""

    def __init__(self, tracker: BeatTracker, library: Library) -> None:
        self._tracker = tracker
        self._library = library
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="beats")
        self._jobs: dict[str, _Job] = {}
        self._decodings: dict[_DecodingKey, DecodedBeats] = {}  # oldest first
        self._lock = threading.Lock()

    def start(self, video_id: str, force: bool = False) -> BeatTrackingState:
        """Detect the beats unless that is running or done; `force` runs the network again."""
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status.is_active:
                return self._state_of(job)
            analysis = self._current_analysis(video_id)
            if not force and analysis is not None:
                return BeatTrackingState(
                    video_id=video_id, status=AnalysisStatus.COMPLETED, analysis=analysis
                )
            job = _Job(video_id, rerun_network=force)
            self._jobs[video_id] = job
            self._executor.submit(self._run, job)
            return self._state_of(job)

    def get_state(self, video_id: str) -> BeatTrackingState:
        self._require_video(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status is not AnalysisStatus.COMPLETED:
                return self._state_of(job)
        analysis = self._current_analysis(video_id)
        if analysis is not None:
            return BeatTrackingState(
                video_id=video_id, status=AnalysisStatus.COMPLETED, analysis=analysis
            )
        return BeatTrackingState(video_id=video_id, status=AnalysisStatus.NOT_STARTED)

    def detected(self, video_id: str) -> BeatAnalysis | None:
        """The detected grid (without anyone's fixes), once detection is done."""
        self._require_video(video_id)
        return self._current_analysis(video_id)

    def grid(self, video_id: str, hints: BeatGridHints) -> BeatAnalysis:
        """The grid decoded with a user's hints, from the stored network output.

        Takes a moment for new tempo or meter hints (decoded once, then kept a while).
        Raises BeatsNotDetectedError until the detection is done.
        """
        self._require_video(video_id)
        detected = self._current_analysis(video_id)
        if detected is None:
            raise BeatsNotDetectedError(video_id)
        if hints == NO_HINTS:
            return detected
        model = self._tracker.model
        key = (video_id, model, hints.beats_per_bar, hints.tempo_bpm)
        with self._lock:
            decoded = self._decodings.get(key)
        if decoded is None:
            activations = self._library.read_beat_activations(video_id)
            if activations is None or activations.model != model:
                raise BeatsNotDetectedError(video_id)
            decoded = decode_grid(activations, hints)
            self._remember(key, decoded)
        return grid_analysis(decoded, model, hints)

    def forget(self, video_id: str) -> None:
        """Drop a finished job, e.g. after its video was deleted."""
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and not job.status.is_active:
                del self._jobs[video_id]
            self._forget_decodings(video_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: _Job) -> None:
        self._update(job, status=AnalysisStatus.ANALYZING)
        media_path = self._library.media_path(job.video_id)
        try:
            if media_path is None:
                raise VideoNotInLibraryError(job.video_id)
            model = self._tracker.model
            key = (job.video_id, model, NO_HINTS.beats_per_bar, NO_HINTS.tempo_bpm)
            with self._lock:
                if job.rerun_network:
                    self._forget_decodings(job.video_id)
                decoded = self._decodings.get(key)
            if decoded is None:
                activations = None
                if not job.rerun_network:
                    activations = self._library.read_beat_activations(job.video_id)
                if activations is None or activations.model != model:
                    activations = self._tracker.activations(media_path)
                    self._library.write_beat_activations(job.video_id, activations)
                decoded = decode_grid(activations, NO_HINTS)
                self._remember(key, decoded)
            analysis = grid_analysis(decoded, model, NO_HINTS)
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

    def _current_analysis(self, video_id: str) -> BeatAnalysis | None:
        """The stored detected grid; None (detect again) if an older method or another
        network made it, or it has hints (from when fixes were shared by everyone)."""
        analysis = self._library.read_beat_analysis(video_id)
        if (
            analysis is None
            or not is_current_analysis(analysis)
            or analysis.analyzer != f"{self._tracker.model}+{GRID_DECODER}"
            or analysis.hints != NO_HINTS
        ):
            return None
        return analysis

    def _remember(self, key: _DecodingKey, decoded: DecodedBeats) -> None:
        with self._lock:
            self._decodings.pop(key, None)
            self._decodings[key] = decoded
            while len(self._decodings) > _DECODINGS_KEPT:
                del self._decodings[next(iter(self._decodings))]

    def _forget_decodings(self, video_id: str) -> None:
        """Caller holds the lock."""
        for key in [k for k in self._decodings if k[0] == video_id]:
            del self._decodings[key]

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
