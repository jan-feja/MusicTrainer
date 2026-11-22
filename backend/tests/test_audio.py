import io
import math
import shutil
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from music_trainer.services.audio import (
    AudioDecodeError,
    decode_audio,
    extract_wav,
    ffmpeg_executable,
)

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def write_sine_wav(
    path: Path, seconds: float = 1.0, sample_rate: int = 44100, click_at: float | None = None
) -> None:
    """A quiet 440 Hz tone, optionally with one loud sample at `click_at` seconds."""
    frames = int(seconds * sample_rate)
    samples = [int(1200 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(frames)]
    if click_at is not None:
        samples[round(click_at * sample_rate)] = 30000
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(sample_rate)
        file.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def read_wav(data: bytes) -> tuple[wave._wave_params, np.ndarray]:
    with wave.open(io.BytesIO(data), "rb") as file:
        params = file.getparams()
        samples = np.frombuffer(file.readframes(params.nframes), dtype="<i2")
    return params, samples.reshape(-1, params.nchannels)


@requires_ffmpeg
def test_decodes_to_mono_float_at_the_requested_rate(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    write_sine_wav(path, seconds=1.0)
    samples = decode_audio(path, 22050)
    assert samples.dtype == np.float32
    assert abs(len(samples) - 22050) < 100
    assert 0.03 < np.abs(samples).max() < 0.04  # 1200 / 32768


@requires_ffmpeg
def test_extracts_a_section_as_stereo_wav(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    write_sine_wav(path, seconds=2.0, sample_rate=48000, click_at=1.25)
    params, samples = read_wav(extract_wav(path, 1.0, 1.5, 48000))
    assert (params.nchannels, params.sampwidth, params.framerate) == (2, 2, 48000)
    assert params.nframes == 24000
    # sample-exact: the click 0.25 s into the section
    assert np.argmax(np.abs(samples[:, 0])) == 12000
    assert np.array_equal(samples[:, 0], samples[:, 1])


@requires_ffmpeg
def test_section_past_the_end_is_shorter(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    write_sine_wav(path, seconds=1.0, sample_rate=44100)
    params, _ = read_wav(extract_wav(path, 0.5, 3.0, 22050))
    assert params.framerate == 22050
    assert abs(params.nframes - 22050 // 2) < 100


@requires_ffmpeg
def test_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"this is not a media file")
    with pytest.raises(AudioDecodeError, match="could not read"):
        decode_audio(path, 22050)


def test_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(AudioDecodeError, match="not found"):
        decode_audio(tmp_path / "x.wav", 22050, ffmpeg="ffmpeg-that-does-not-exist")


def test_ffmpeg_executable(tmp_path: Path) -> None:
    assert ffmpeg_executable(None) == "ffmpeg"
    assert ffmpeg_executable(tmp_path) == str(tmp_path / "ffmpeg")
    assert ffmpeg_executable(tmp_path / "my-ffmpeg.exe") == str(tmp_path / "my-ffmpeg.exe")
