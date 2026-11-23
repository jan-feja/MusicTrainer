"""Reading audio out of downloaded media files with ffmpeg."""

import io
import subprocess
import wave
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


def decode_audio(
    path: Path, sample_rate: int, ffmpeg: str = "ffmpeg", channels: int = 1
) -> np.ndarray:
    """Decode the audio of any media file to float32 samples at `sample_rate`.

    Mono gives shape (samples,); more channels give (samples, channels).
    """
    output = _run_ffmpeg(
        path,
        ffmpeg,
        ["-i", str(path), "-vn", "-ac", str(channels), "-ar", str(sample_rate), "-f", "f32le"],
    )
    samples = np.frombuffer(output, dtype=np.float32)
    if samples.size == 0:
        raise AudioDecodeError(f"{path.name} contains no audio")
    return samples if channels == 1 else samples.reshape(-1, channels)


def write_flac(path: Path, samples: np.ndarray, sample_rate: int, ffmpeg: str = "ffmpeg") -> None:
    """Write float samples, shape (samples, channels), as a 16-bit FLAC file."""
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    pcm = np.clip(samples, -1, 1).astype("<f4").tobytes()
    command = [
        *(ffmpeg, "-v", "error", "-nostdin", "-y"),
        *("-f", "f32le", "-ar", str(sample_rate), "-ac", str(channels), "-i", "-"),
        *("-c:a", "flac", "-sample_fmt", "s16", str(path)),
    ]
    try:
        subprocess.run(command, input=pcm, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise AudioDecodeError(
            f"ffmpeg not found ({ffmpeg}); install it or set its path"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip()[-300:]
        raise AudioDecodeError(f"ffmpeg could not write {path.name}: {detail}") from error


def extract_wav(
    path: Path, start: float, end: float, sample_rate: int, ffmpeg: str = "ffmpeg"
) -> bytes:
    """
    The audio from `start` to `end` seconds as a 16-bit stereo WAV file.

    Sample-exact: the first sample is the one the browser plays at `start`.
    Shorter than asked when the media ends earlier.
    """
    output = _run_ffmpeg(
        path,
        ffmpeg,
        [
            *("-ss", f"{start:.6f}", "-i", str(path), "-t", f"{end - start:.6f}"),
            *("-vn", "-ac", "2", "-ar", str(sample_rate), "-f", "s16le"),
        ],
    )
    # written here rather than by ffmpeg, which cannot fill in the sizes when writing to a pipe
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(sample_rate)
        file.writeframes(output)
    return buffer.getvalue()


def _run_ffmpeg(path: Path, ffmpeg: str, arguments: list[str]) -> bytes:
    command = [ffmpeg, "-v", "error", "-nostdin", *arguments, "-"]
    try:
        result = subprocess.run(command, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise AudioDecodeError(
            f"ffmpeg not found ({ffmpeg}); install it or set its path"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip()[-300:]
        raise AudioDecodeError(f"ffmpeg could not read {path.name}: {detail}") from error
    return result.stdout
