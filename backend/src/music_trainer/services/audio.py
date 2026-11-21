"""Reading audio out of downloaded media files with ffmpeg."""

import subprocess
from pathlib import Path

import numpy as np


class AudioDecodeError(Exception):
    """ffmpeg is missing or could not read the file."""


def ffmpeg_executable(configured: Path | None) -> str:
    """The ffmpeg command to run; `configured` may be the executable or its folder."""
    if configured is None:
        return "ffmpeg"
    if configured.is_dir():
        return str(configured / "ffmpeg")
    return str(configured)


def decode_audio(path: Path, sample_rate: int, ffmpeg: str = "ffmpeg") -> np.ndarray:
    """Decode the audio of any media file to mono float32 samples at `sample_rate`."""
    command = [
        ffmpeg,
        *("-v", "error", "-nostdin", "-i", str(path)),
        *("-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise AudioDecodeError(
            f"ffmpeg not found ({ffmpeg}); install it or set its path"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip()[-300:]
        raise AudioDecodeError(f"ffmpeg could not read {path.name}: {detail}") from error
    samples = np.frombuffer(result.stdout, dtype=np.float32)
    if samples.size == 0:
        raise AudioDecodeError(f"{path.name} contains no audio")
    return samples
