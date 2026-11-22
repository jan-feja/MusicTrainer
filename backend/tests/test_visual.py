"""Pictures of the music: spectrogram and section colors."""

import numpy as np

from music_trainer.services.visual import BANDS, COLOR_STEP, FPS, SAMPLE_RATE, compute_picture


def tone(freq: float, seconds: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_spectrogram_shape_and_scale() -> None:
    picture = compute_picture(tone(440, 4.0))
    assert picture.spectrogram.dtype == np.uint8
    assert picture.spectrogram.shape[1] == BANDS
    assert abs(len(picture.spectrogram) - 4.0 * FPS) <= 2
    assert picture.spectrogram.max() == 255


def test_a_low_tone_is_low_in_the_spectrogram() -> None:
    low = compute_picture(tone(110, 3.0)).spectrogram.mean(axis=0)
    high = compute_picture(tone(3520, 3.0)).spectrogram.mean(axis=0)
    assert int(np.argmax(low)) < int(np.argmax(high))


def test_music_that_returns_gets_its_color_again() -> None:
    """A minute of a low tone, a minute of a chord, the tone again: A B A in color."""
    chord = tone(330, 60.0, 0.1) + tone(415, 60.0, 0.1) + tone(494, 60.0, 0.1)
    picture = compute_picture(np.concatenate([tone(110, 60.0), chord, tone(110, 60.0)]))
    colors = picture.colors.astype(float)
    assert colors.shape == (int(180 / COLOR_STEP), 3)
    n = len(colors)
    first, middle, last = (
        colors[int(n * a) : int(n * b)] for a, b in ((0.1, 0.23), (0.43, 0.56), (0.77, 0.9))
    )
    assert np.abs(first.mean(axis=0) - last.mean(axis=0)).max() < 10
    assert np.abs(first.mean(axis=0) - middle.mean(axis=0)).max() > 60
    for block in (first, middle, last):
        assert np.abs(block - block.mean(axis=0)).max() < 25


def test_silence_does_not_fail() -> None:
    picture = compute_picture(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert picture.spectrogram.shape[1] == BANDS
