"""Beat and bar detection with Beat This! (Foscarin, Schlüter, Widmer, ISMIR 2024).

Chosen after testing (docs/implementation-report.md, experiments/test_beats_followup.py):
on real songs it finds 86 % of beats and 82 % of bar starts, and both ends of
a 1-4 bar loop land on the right bar lines in ~87 % of cases; it is weakest in
soft intros without drums. A 4-minute song takes about 9 s on a laptop CPU.
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

from music_trainer.models import BeatAnalysis
from music_trainer.services.audio import decode_audio

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
    """Finds beats and bar starts in a media file. Tests replace it with a fake."""

    def analyze(self, media_path: Path) -> BeatAnalysis: ...


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
    """BeatTracker using a Beat This! model; the model loads on first use."""

    def __init__(
        self, model_name: str, models_dir: Path, device: str = "cpu", ffmpeg: str = "ffmpeg"
    ) -> None:
        self._model_name = model_name
        self._checkpoint = models_dir / f"beat_this-{model_name}.ckpt"
        self._device = device
        self._ffmpeg = ffmpeg
        self._model = None
        self._lock = threading.Lock()

    def analyze(self, media_path: Path) -> BeatAnalysis:
        samples = decode_audio(media_path, SAMPLE_RATE, self._ffmpeg)
        with self._lock:  # one inference at a time; the model is not thread-safe
            beats, downbeats = self._load_model()(samples, SAMPLE_RATE)
        return beat_analysis_from_times(beats, downbeats, f"beat_this:{self._model_name}")

    def _load_model(self):
        if self._model is None:
            from beat_this.inference import (
                Audio2Beats,
            )  # imports PyTorch: slow, so only when needed

            checkpoint = ensure_checkpoint(beat_this_checkpoint(self._model_name), self._checkpoint)
            self._model = Audio2Beats(str(checkpoint), device=self._device, dbn=False)
        return self._model


def beat_analysis_from_times(
    beats: Sequence[float], downbeats: Sequence[float], analyzer: str
) -> BeatAnalysis:
    """Build the stored beat grid from raw detector output."""
    beat_times = sorted(round(float(t), 3) for t in beats)
    # bar starts must be beats (the UI snaps to both); the detector already does this,
    # snapping again only guards against rounding
    bar_starts = sorted({_nearest(beat_times, float(t)) for t in downbeats}) if beat_times else []
    return BeatAnalysis(
        bpm=estimate_bpm(beat_times),
        beats_per_bar=most_common_bar_length(beat_times, bar_starts),
        beats=beat_times,
        downbeats=bar_starts,
        analyzer=analyzer,
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
