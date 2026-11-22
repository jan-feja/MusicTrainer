"""Chords on the beat grid: chroma, chord templates and smoothing over beats.

1. Chroma: how strong each of the 12 pitch classes (C, C#, ... B) is, from a
   constant-Q transform (librosa), tuned to the recording.
2. Averaged between consecutive beats, so chords can change only on beats.
3. Each beat is compared with major and minor triad templates (and "no chord").
4. A Viterbi pass prefers staying on a chord: one odd beat does not make a new chord.

From the experiments (docs/implementation-report.md, feature 12): 95-98 % right on
a synthetic song, plausible but jumpy on real songs; the beat averaging and the
smoothing are what the report asked for next. With stems, only the pitched ones
(bass, guitar, piano, other) are used: no drums or vocals to blur the harmony.
"""

import hashlib
import itertools
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from music_trainer.models import BeatAnalysis, Chord
from music_trainer.services.audio import decode_audio

SAMPLE_RATE = 22050
HOP_LENGTH = 512
METHOD = "chroma-templates+beats"
NO_CHORD = "N"
PITCH_CLASSES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
HARMONIC_STEMS = ("bass", "guitar", "piano", "other")

# chance of the next beat keeping the chord; the rest is spread over the other chords
_STAY = 0.85
# how sharply the template match decides between chords
_SHARPNESS = 12.0
# a beat this much quieter than the song's typical beat is "no chord"
_SILENT_SHARE = 0.05


class ChordDetectionError(Exception):
    """Chords could not be detected (no beat grid yet, unreadable audio, ...)."""


class ChordDetector(Protocol):
    """Finds the chords of a song on its beat grid. Tests replace it with a fake."""

    @property
    def method(self) -> str: ...

    def detect(
        self, media_path: Path, stem_paths: Sequence[Path], beats: Sequence[float]
    ) -> list[Chord]:
        """`stem_paths`: the pitched stems, if separated; otherwise the media's audio is used."""
        ...


def beat_grid_key(analysis: BeatAnalysis) -> str:
    """Identifies a beat grid: chords made on another grid are detected again."""
    data = json.dumps([round(b, 3) for b in analysis.beats]).encode()
    return hashlib.sha256(data).hexdigest()[:16]


def chord_templates() -> tuple[list[str], np.ndarray]:
    """Labels ('C:maj', 'A:min', ..., 'N') and unit-length templates, one row each."""
    labels: list[str] = []
    rows: list[np.ndarray] = []
    for root, name in enumerate(PITCH_CLASSES):
        for quality, intervals in (("maj", (0, 4, 7)), ("min", (0, 3, 7))):
            row = np.zeros(12)
            row[[(root + i) % 12 for i in intervals]] = 1
            labels.append(f"{name}:{quality}")
            rows.append(row / np.linalg.norm(row))
    labels.append(NO_CHORD)
    rows.append(np.full(12, 0.5 / np.sqrt(12)))  # matches flat chroma, never strongly
    return labels, np.array(rows)


def segment_bounds(beats: Sequence[float], duration: float) -> np.ndarray:
    """Segment boundaries: the start, every beat inside the song, and the end."""
    inner = [b for b in beats if 0 < b < duration]
    return np.array([0.0, *inner, duration])


def segment_chroma(chroma: np.ndarray, bounds: np.ndarray, frame_rate: float) -> np.ndarray:
    """Mean chroma of each segment, shape (segments, 12)."""
    frames = np.round(bounds * frame_rate).astype(int)
    last = chroma.shape[1] - 1
    result = np.zeros((len(bounds) - 1, 12))
    for i, (start, end) in enumerate(itertools.pairwise(frames)):
        start = min(start, last)
        end = min(max(end, start + 1), last + 1)
        result[i] = chroma[:, start:end].mean(axis=1)
    return result


def viterbi(log_emission: np.ndarray, stay: float) -> np.ndarray:
    """Most likely state per step, shape (steps,), from log_emission (steps, states)."""
    steps, states = log_emission.shape
    log_stay = np.log(stay)
    log_move = np.log((1 - stay) / (states - 1))
    score = log_emission[0].copy()
    back = np.zeros((steps, states), dtype=int)
    for t in range(1, steps):
        best_previous = int(np.argmax(score))
        moved = score[best_previous] + log_move
        stayed = score + log_stay
        back[t] = np.where(stayed >= moved, np.arange(states), best_previous)
        score = np.maximum(stayed, moved) + log_emission[t]
    path = np.zeros(steps, dtype=int)
    path[-1] = int(np.argmax(score))
    for t in range(steps - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def label_segments(beat_chroma: np.ndarray, loudness: np.ndarray, stay: float = _STAY) -> list[str]:
    """A chord label per segment from its mean chroma and loudness."""
    labels, templates = chord_templates()
    norms = np.linalg.norm(beat_chroma, axis=1, keepdims=True)
    unit = beat_chroma / np.maximum(norms, 1e-9)
    scores = _SHARPNESS * unit @ templates.T
    log_emission = scores - np.log(np.exp(scores).sum(axis=1, keepdims=True))
    # (nearly) silent segments: no chord
    typical = np.median(loudness[loudness > 0]) if np.any(loudness > 0) else 0
    silent = loudness <= typical * _SILENT_SHARE
    log_emission[silent] = np.log(1e-6)
    log_emission[silent, len(labels) - 1] = 0
    return [labels[i] for i in viterbi(log_emission, stay)]


def merge_segments(bounds: np.ndarray, labels: Sequence[str]) -> list[Chord]:
    """Consecutive segments with the same chord become one Chord."""
    chords: list[Chord] = []
    for start, end, label in zip(bounds[:-1], bounds[1:], labels, strict=True):
        if end <= start:
            continue
        if chords and chords[-1].label == label:
            chords[-1] = chords[-1].model_copy(update={"end": round(float(end), 3)})
        else:
            chords.append(
                Chord(start=round(float(start), 3), end=round(float(end), 3), label=label)
            )
    return chords


def detect_chords(
    samples: np.ndarray, sample_rate: int, beats: Sequence[float], separate_harmonics: bool
) -> list[Chord]:
    """The chords of mono `samples`, changing only on `beats` (seconds)."""
    import librosa  # slow to import, so only here

    duration = len(samples) / sample_rate
    if duration <= 0:
        return []
    if separate_harmonics:  # leave out the drums of a full mix
        samples = librosa.effects.harmonic(samples)
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate, hop_length=HOP_LENGTH)
    rms = librosa.feature.rms(y=samples, hop_length=HOP_LENGTH)
    bounds = segment_bounds(beats, duration)
    frame_rate = sample_rate / HOP_LENGTH
    labels = label_segments(
        segment_chroma(chroma, bounds, frame_rate),
        segment_chroma(np.repeat(rms, 12, axis=0), bounds, frame_rate)[:, 0],
    )
    return merge_segments(bounds, labels)


class LibrosaChordDetector:
    """ChordDetector on the pitched stems if there are any, else on the whole mix."""

    method = METHOD

    def __init__(self, ffmpeg: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg

    def detect(
        self, media_path: Path, stem_paths: Sequence[Path], beats: Sequence[float]
    ) -> list[Chord]:
        if stem_paths:
            stems = [decode_audio(path, SAMPLE_RATE, self._ffmpeg) for path in stem_paths]
            length = min(len(stem) for stem in stems)
            samples = np.sum([stem[:length] for stem in stems], axis=0)
        else:
            samples = decode_audio(media_path, SAMPLE_RATE, self._ffmpeg)
        return detect_chords(samples, SAMPLE_RATE, beats, separate_harmonics=not stem_paths)
