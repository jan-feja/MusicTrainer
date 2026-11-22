"""Runs the real Demucs model (downloaded on first run, ~80 MB). `pytest -m network`."""

import wave
from pathlib import Path

import numpy as np
import pytest

from music_trainer.services.audio import decode_audio
from music_trainer.services.stems import DemucsSeparator

pytestmark = pytest.mark.network

SAMPLE_RATE = 44100
SECONDS = 10


def write_drums_and_bass(path: Path) -> None:
    """A kick drum every half second over a steady low bass note."""
    t = np.arange(SECONDS * SAMPLE_RATE) / SAMPLE_RATE
    bass = 0.3 * np.sin(2 * np.pi * 55 * t)
    since_kick = t % 0.5
    kick = (
        0.8
        * np.exp(-since_kick * 30)
        * np.sin(2 * np.pi * (60 + 200 * np.exp(-since_kick * 40)) * since_kick)
    )
    noise = np.random.default_rng(0).standard_normal(t.size)
    snare = 0.4 * np.exp(-((t - 0.25) % 0.5) * 40) * noise
    mix = np.clip(bass + kick + snare, -1, 1)
    pcm = (np.repeat(mix[:, None], 2, axis=1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(pcm.tobytes())


def test_demucs_separates_drums_from_bass(tmp_path: Path) -> None:
    song = tmp_path / "song.wav"
    write_drums_and_bass(song)
    out_dir = tmp_path / "stems"
    out_dir.mkdir()
    progress: list[float] = []

    stems = DemucsSeparator("htdemucs_6s", tmp_path / "models").separate(
        song, out_dir, progress.append
    )

    names = [stem.name for stem in stems.stems]
    assert sorted(names) == ["bass", "drums", "guitar", "other", "piano", "vocals"]
    assert stems.duration == pytest.approx(SECONDS, abs=0.01)
    assert progress and progress == sorted(progress) and progress[-1] > 0.8
    for stem in stems.stems:
        samples = decode_audio(out_dir / stem.file, SAMPLE_RATE, channels=2)
        assert len(samples) == SECONDS * SAMPLE_RATE  # all the same length as the song
    rms = {stem.name: stem.rms for stem in stems.stems}
    assert rms["drums"] > 3 * rms["vocals"]
    assert rms["bass"] > 3 * rms["vocals"]
