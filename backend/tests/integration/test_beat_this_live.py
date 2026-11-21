"""Runs the real Beat This! model (downloaded on first run, ~78 MB). `pytest -m network`."""

import math
import struct
import wave
from pathlib import Path

import pytest

from music_trainer.config import Settings
from music_trainer.services.beats import BeatThisTracker

pytestmark = pytest.mark.network

BPM = 120
BEATS_PER_BAR = 4
SECONDS = 24
SAMPLE_RATE = 44100


def write_drum_loop(path: Path) -> list[float]:
    """A simple 4/4 groove: kick on 1 and 3, snare on 2 and 4, hi-hat on eighths.

    Returns the beat times. The first beat comes after 1 s of silence.
    """
    samples = [0.0] * (SECONDS * SAMPLE_RATE)

    def hit(start: float, freq: float, length: float, gain: float, noise: bool = False) -> None:
        begin = int(start * SAMPLE_RATE)
        for i in range(int(length * SAMPLE_RATE)):
            if begin + i >= len(samples):
                break
            envelope = math.exp(-i / (0.15 * length * SAMPLE_RATE))
            tone = (
                ((i * 7919) % 200) / 100 - 1
                if noise
                else math.sin(2 * math.pi * freq * i / SAMPLE_RATE)
            )
            samples[begin + i] += gain * envelope * tone

    period = 60 / BPM
    beats = []
    start = 1.0
    while start + period < SECONDS:
        index = len(beats)
        beats.append(start)
        if index % 2 == 0:
            hit(start, 55, 0.4, 0.8)  # kick
        else:
            hit(start, 180, 0.2, 0.5, noise=True)  # snare
        hit(start, 0, 0.05, 0.15, noise=True)  # hi-hat on the beat
        hit(start + period / 2, 0, 0.05, 0.1, noise=True)  # ... and in between
        if index % BEATS_PER_BAR == 0:
            hit(start, 110, 0.6, 0.4)  # bass note marks the bar start
        start += period
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        peak = max(abs(s) for s in samples)
        file.writeframes(b"".join(struct.pack("<h", int(s / peak * 30000)) for s in samples))
    return beats


def test_detects_tempo_beats_and_bars(tmp_path: Path) -> None:
    true_beats = write_drum_loop(tmp_path / "groove.wav")
    tracker = BeatThisTracker("final0", Settings().models_dir)

    analysis = tracker.analyze(tmp_path / "groove.wav")

    assert analysis.bpm == pytest.approx(BPM, abs=2)
    assert analysis.beats_per_bar == BEATS_PER_BAR
    found = [b for b in true_beats if any(abs(b - d) < 0.05 for d in analysis.beats)]
    assert len(found) >= 0.9 * len(true_beats)
    assert set(analysis.downbeats) <= set(analysis.beats)
