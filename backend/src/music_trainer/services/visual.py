"""Pictures of the music for the grid editor: a spectrogram and section colors (numpy only).

- **Spectrogram:** 64 mel bands (30 Hz - 11 kHz), 50 frames per second like the beat network,
  in dB, the loudest 0.5 % at 255. Onsets show as vertical lines, notes as horizontal ones.
- **Section colors:** one color per 0.2 s; similar music gets a similar color, so sections
  tend to stand out as blocks and a chorus that comes back gets its color again. Timbre (16
  coarse mel bands) and harmony (12 pitch classes), smoothed over a few seconds, projected on
  their 3 main directions (PCA) and mapped to hue, saturation and brightness. A hint, not a
  detector: on 38 Harmonix songs, 43 % of the annotated section starts are among a song's
  largest 20 % of color changes (27 % for random times; experiments/test_section_colors.py).
"""

from dataclasses import dataclass

import numpy as np

VERSION = 1  # stored with the picture; a new version computes it again
SAMPLE_RATE = 22050
FPS = 50
N_FFT = 2048
BANDS = 64
F_MIN, F_MAX = 30.0, 11000.0
COLOR_STEP = 0.2  # seconds per color (a whole number of frames)
COLOR_SMOOTHING = 8.0  # seconds: half-width of the smoothing window
DB_RANGE = 70.0
CHUNK_FRAMES = 4000  # frames per FFT batch (bounds memory for long videos)


@dataclass(frozen=True)
class MusicPicture:
    spectrogram: np.ndarray
    """uint8 [frames, BANDS], low frequencies first."""
    colors: np.ndarray
    """uint8 [steps, 3] RGB, one per COLOR_STEP seconds."""
    fps: float = FPS
    color_step: float = COLOR_STEP


def compute_picture(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> MusicPicture:
    """The picture of mono samples at SAMPLE_RATE."""
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"samples must be at {SAMPLE_RATE} Hz")
    magnitude = _stft_magnitude(samples, N_FFT, SAMPLE_RATE // FPS)
    mel = magnitude @ _mel_filters().T
    chroma = magnitude @ _chroma_filters().T
    return MusicPicture(_spectrogram(mel), _section_colors(mel, chroma))


def _stft_magnitude(samples: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    """|STFT| with frames centred on t = i * hop, computed in batches."""
    window = np.hanning(n_fft).astype(np.float32)
    padded = np.concatenate(
        [
            np.zeros(n_fft // 2, np.float32),
            samples.astype(np.float32),
            np.zeros(n_fft // 2, np.float32),
        ]
    )
    count = max(1, 1 + (len(padded) - n_fft) // hop)
    out = np.empty((count, n_fft // 2 + 1), dtype=np.float32)
    for start in range(0, count, CHUNK_FRAMES):
        end = min(count, start + CHUNK_FRAMES)
        index = (np.arange(start, end) * hop)[:, None] + np.arange(n_fft)[None, :]
        index = np.minimum(index, len(padded) - 1)
        out[start:end] = np.abs(np.fft.rfft(padded[index] * window, axis=1))
    return out


def _mel_filters() -> np.ndarray:
    def to_mel(f):
        return 2595 * np.log10(1 + f / 700)

    def to_hz(m):
        return 700 * (10 ** (m / 2595) - 1)

    freqs = np.fft.rfftfreq(N_FFT, 1 / SAMPLE_RATE)
    edges = to_hz(np.linspace(to_mel(F_MIN), to_mel(F_MAX), BANDS + 2))
    filters = np.zeros((BANDS, len(freqs)), dtype=np.float32)
    for m in range(BANDS):
        low, mid, high = edges[m : m + 3]
        filters[m] = np.maximum(
            0, np.minimum((freqs - low) / (mid - low), (high - freqs) / (high - mid))
        )
        filters[m] /= max(filters[m].sum(), 1e-9)
    return filters


def _chroma_filters() -> np.ndarray:
    """Pitch class of every FFT bin from 55 Hz to 4 kHz, weighted by closeness to a semitone."""
    freqs = np.fft.rfftfreq(N_FFT, 1 / SAMPLE_RATE)
    filters = np.zeros((12, len(freqs)), dtype=np.float32)
    used = np.flatnonzero((freqs >= 55) & (freqs <= 4000))
    pitch = 12 * np.log2(freqs[used] / 440.0) + 69
    nearest = np.round(pitch)
    filters[nearest.astype(int) % 12, used] = np.exp(-0.5 * ((pitch - nearest) / 0.3) ** 2)
    return filters


def _spectrogram(mel: np.ndarray) -> np.ndarray:
    db = 20 * np.log10(np.maximum(mel, 1e-9))
    top = np.percentile(db, 99.5) if db.size else 0.0
    scaled = np.clip((db - (top - DB_RANGE)) / DB_RANGE, 0, 1)
    return np.round(scaled * 255).astype(np.uint8)


def _section_colors(mel: np.ndarray, chroma: np.ndarray) -> np.ndarray:
    per_step = round(COLOR_STEP * FPS)
    steps = len(mel) // per_step
    if steps < 2:
        return np.full((max(steps, 0), 3), 128, dtype=np.uint8)
    timbre = np.log(mel[: steps * per_step].reshape(steps, per_step, -1).mean(1) + 1e-6)
    timbre = timbre.reshape(steps, 16, BANDS // 16).mean(2)
    harmony = chroma[: steps * per_step].reshape(steps, per_step, -1).mean(1)
    harmony /= np.linalg.norm(harmony, axis=1, keepdims=True) + 1e-9
    x = np.concatenate([_standardize(timbre), _standardize(harmony)], axis=1)
    width = int(COLOR_SMOOTHING / COLOR_STEP)
    kernel = np.hanning(2 * width + 1)
    kernel /= kernel.sum()
    x = np.stack(
        [
            np.convolve(np.pad(x[:, j], width, mode="edge"), kernel, mode="valid")
            for j in range(x.shape[1])
        ],
        axis=1,
    )
    x -= x.mean(axis=0)
    _, _, directions = np.linalg.svd(x, full_matrices=False)
    p = x @ directions[:3].T
    if p.shape[1] < 3:
        p = np.pad(p, ((0, 0), (0, 3 - p.shape[1])))
    low, high = np.percentile(p, 2, axis=0), np.percentile(p, 98, axis=0)
    p = np.clip((p - low) / (high - low + 1e-9), 0, 1)
    hue = (np.arctan2(p[:, 2] - 0.5, p[:, 1] - 0.5) / (2 * np.pi)) % 1.0
    saturation = np.clip(0.35 + 1.3 * np.hypot(p[:, 1] - 0.5, p[:, 2] - 0.5), 0, 1)
    value = 0.45 + 0.5 * p[:, 0]
    return np.round(_hsv_to_rgb(hue, saturation, value) * 255).astype(np.uint8)


def _standardize(x: np.ndarray) -> np.ndarray:
    return (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-9)


def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=1)
