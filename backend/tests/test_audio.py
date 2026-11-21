import math
import shutil
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from music_trainer.services.audio import AudioDecodeError, decode_audio, ffmpeg_executable

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def write_sine_wav(path: Path, seconds: float = 1.0, sample_rate: int = 44100) -> None:
    frames = int(seconds * sample_rate)
    samples = (int(12000 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(frames))
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(sample_rate)
        file.writeframes(b"".join(struct.pack("<h", s) for s in samples))


@requires_ffmpeg
def test_decodes_to_mono_float_at_the_requested_rate(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    write_sine_wav(path, seconds=1.0)
    samples = decode_audio(path, 22050)
    assert samples.dtype == np.float32
    assert abs(len(samples) - 22050) < 100
    assert 0.3 < np.abs(samples).max() < 0.4  # 12000 / 32768


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
