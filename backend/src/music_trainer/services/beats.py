"""Beat and bar detection: Beat This! (Foscarin, Schlüter, Widmer, ISMIR 2024) + grid decoding.

The network says, 50 times per second, how likely a beat and a bar start are
(about 9 s for a 4-minute song on a laptop CPU). beat_decoding.py turns that
into a beat grid with steady bars. The network output is stored with the video,
so the grid can be decoded again in a moment with the user's hints.
Measured in experiments/test_beat_tracking.py.
"""

import hashlib
import itertools
import logging
import statistics
import threading
import urllib.request
from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from music_trainer.models import BeatAnalysis, BeatGridHints
from music_trainer.services.audio import decode_audio
from music_trainer.services.beat_decoding import (
    FRAMES_PER_SECOND,
    BeatActivations,
    DecodedBeats,
    DecodingOptions,
    decode_beats,
    fit_steady_tempo,
    place_bar_starts,
)

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050  # what the Beat This! models were trained on
_CHECKPOINT_URL = "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/{name}.ckpt"
_KNOWN_CHECKPOINTS = {  # SHA-256 of the published files, checked after download
    "final0": "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331",
    "small0": "6074be2c4d490c5f6101fcc374a1ec72ae93456e23bb6019783b849f5dc7d47b",
}


class BeatTrackingError(Exception):
    """Beat detection could not run (model missing, download failed, ...)."""


class BeatTracker(Protocol):
    """Runs the beat network on a media file. Tests replace it with a fake."""

    @property
    def model(self) -> str:
        """Name of the network, stored with its output, e.g. 'beat_this:final0'."""
        ...

    def activations(self, media_path: Path) -> BeatActivations: ...


@dataclass(frozen=True)
class CheckpointSource:
    url: str
    sha256: str | None
    """Expected checksum; None skips the check (unknown model names)."""


def beat_this_checkpoint(name: str) -> CheckpointSource:
    return CheckpointSource(_CHECKPOINT_URL.format(name=name), _KNOWN_CHECKPOINTS.get(name))


def ensure_checkpoint(source: CheckpointSource, target: Path) -> Path:
    """Download the model file to `target` unless it is already there."""
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    logger.info("Downloading beat model %s", source.url)
    request = urllib.request.Request(source.url, headers={"User-Agent": "music-trainer"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as file:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                file.write(chunk)
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise BeatTrackingError(
            f"Could not download the beat model ({error}). Download {source.url} "
            f"by hand and save it as {target}."
        ) from error
    if source.sha256 is not None and digest.hexdigest() != source.sha256:
        partial.unlink(missing_ok=True)
        raise BeatTrackingError(f"The downloaded beat model {source.url} is corrupt (checksum)")
    partial.replace(target)
    return target


class BeatThisTracker:
    """BeatTracker using a Beat This! network; it loads on first use."""

    def __init__(
        self, model_name: str, models_dir: Path, device: str = "cpu", ffmpeg: str = "ffmpeg"
    ) -> None:
        self._model_name = model_name
        self._checkpoint = models_dir / f"beat_this-{model_name}.ckpt"
        self._device = device
        self._ffmpeg = ffmpeg
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self) -> str:
        return f"beat_this:{self._model_name}"

    def activations(self, media_path: Path) -> BeatActivations:
        samples = decode_audio(media_path, SAMPLE_RATE, self._ffmpeg)
        with self._lock:  # one inference at a time; the model is not thread-safe
            beat, downbeat = self._load_model()(samples, SAMPLE_RATE)
        return BeatActivations(
            beat=beat.cpu().numpy(),
            downbeat=downbeat.cpu().numpy(),
            fps=FRAMES_PER_SECOND,
            model=self.model,
        )

    def _load_model(self):
        if self._model is None:
            # imports PyTorch: slow, so only when needed
            from beat_this.inference import Audio2Frames

            checkpoint = ensure_checkpoint(beat_this_checkpoint(self._model_name), self._checkpoint)
            self._model = Audio2Frames(str(checkpoint), device=self._device)
        return self._model


GRID_DECODER = "grid"
"""Suffix of the analyzer name for grids from beat_decoding.py."""
NO_HINTS = BeatGridHints()


def is_current_analysis(analysis: BeatAnalysis) -> bool:
    """False for grids from the first version (peak picking: bars of uneven length)."""
    return analysis.analyzer.endswith(f"+{GRID_DECODER}")


def decode_grid(activations: BeatActivations, hints: BeatGridHints = NO_HINTS) -> DecodedBeats:
    """Decode the network output with the tempo and meter hints (not the bar starts)."""
    return decode_beats(
        activations.beat,
        activations.downbeat,
        DecodingOptions(beats_per_bar=hints.beats_per_bar, tempo_bpm=hints.tempo_bpm),
        fps=activations.fps,
    )


def grid_analysis(decoded: DecodedBeats, model: str, hints: BeatGridHints) -> BeatAnalysis:
    """The stored beat grid: a decoded grid with the user's steady tempo and bar starts."""
    if hints.steady_tempo:
        decoded = fit_steady_tempo(decoded)
    placed = place_bar_starts(decoded, hints.bar_starts)
    return beat_analysis_from_times(
        placed.beats,
        placed.downbeats,
        analyzer=f"{model}+{GRID_DECODER}",
        beats_per_bar=placed.beats_per_bar,
        hints=hints,
    )


def analyze_activations(
    activations: BeatActivations, hints: BeatGridHints = NO_HINTS
) -> BeatAnalysis:
    """Decode the network output into the stored beat grid."""
    return grid_analysis(decode_grid(activations, hints), activations.model, hints)


def beat_analysis_from_times(
    beats: Sequence[float],
    downbeats: Sequence[float],
    analyzer: str,
    beats_per_bar: int | None = None,
    hints: BeatGridHints = NO_HINTS,
) -> BeatAnalysis:
    """Build the stored beat grid from beat and bar-start times."""
    beat_times = sorted(round(float(t), 3) for t in beats)
    # bar starts must be beats (the UI snaps to both); snapping guards against rounding
    bar_starts = sorted({_nearest(beat_times, float(t)) for t in downbeats}) if beat_times else []
    return BeatAnalysis(
        bpm=estimate_bpm(beat_times),
        beats_per_bar=beats_per_bar or most_common_bar_length(beat_times, bar_starts),
        beats=beat_times,
        downbeats=bar_starts,
        analyzer=analyzer,
        hints=hints,
    )


def estimate_bpm(beats: Sequence[float]) -> float | None:
    if len(beats) < 2:
        return None
    intervals = [b - a for a, b in itertools.pairwise(beats) if b > a]
    return round(60 / statistics.median(intervals), 1) if intervals else None


def most_common_bar_length(beats: Sequence[float], downbeats: Sequence[float]) -> int | None:
    if len(downbeats) < 2:
        return None
    indices = [bisect_left(beats, t) for t in downbeats]
    lengths = Counter(b - a for a, b in itertools.pairwise(indices) if b > a)
    return lengths.most_common(1)[0][0] if lengths else None


def _nearest(sorted_times: Sequence[float], t: float) -> float:
    i = bisect_left(sorted_times, t)
    candidates = sorted_times[max(i - 1, 0) : i + 1]
    return min(candidates, key=lambda c: abs(c - t))
