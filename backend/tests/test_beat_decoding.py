"""Beat grid decoding on synthetic network outputs (no model needed)."""

import numpy as np
import pytest

from music_trainer.services.beat_decoding import DecodingOptions, decode_beats, place_bar_starts
from tests.fakes import network_output


def grid(
    bpm: float, beats_per_bar: int, bars: int, start: float = 1.0
) -> tuple[list[float], list[float]]:
    beats = [start + i * 60 / bpm for i in range(beats_per_bar * bars)]
    return beats, beats[::beats_per_bar]


def bar_lengths(result) -> list[int]:
    indices = np.searchsorted(result.beats, result.downbeats - 1e-6)
    return np.diff(indices).tolist()


def test_steady_four_four_is_found_exactly() -> None:
    beats, downbeats = grid(120, 4, 24)
    result = decode_beats(*network_output(beats, downbeats, 51))
    assert result.beats_per_bar == 4
    assert len(result.beats) == len(beats)
    assert np.max(np.abs(result.beats - beats)) < 0.005
    assert np.max(np.abs(result.downbeats - downbeats)) < 0.005


@pytest.mark.parametrize("beats_per_bar", [3, 5, 7])
def test_other_meters(beats_per_bar: int) -> None:
    beats, downbeats = grid(110, beats_per_bar, 16)
    result = decode_beats(*network_output(beats, downbeats, len(beats) * 60 / 110 + 2))
    assert result.beats_per_bar == beats_per_bar
    assert set(bar_lengths(result)) == {beats_per_bar}


def test_false_bar_starts_in_the_middle_of_bars_are_ignored() -> None:
    """The Cryin' failure: the network also sees bar starts at half bars for a while."""
    beats, downbeats = grid(75, 4, 40)
    halves = {b: 0.75 for b in beats[2::4][10:18]}  # bars 10-17: strong 'bar start' on beat 3 too
    result = decode_beats(*network_output(beats, downbeats, 132, extra_downbeats=halves))
    assert result.beats_per_bar == 4
    assert set(bar_lengths(result)) == {4}
    assert np.max(np.abs(result.downbeats - downbeats)) < 0.005


def test_double_time_section_does_not_change_the_tempo() -> None:
    """The network hears eighth notes as beats in one section; the grid keeps one tempo."""
    beats, downbeats = grid(75, 4, 32)
    eighths = [b + 0.4 for b in beats[48:80]]  # bars 12-19 get beats in between as well
    result = decode_beats(*network_output(sorted(beats + eighths), downbeats, 106))
    intervals = np.diff(result.beats)
    assert np.allclose(intervals, 0.8, atol=0.03)


def test_a_single_short_bar_keeps_the_bars_equal() -> None:
    """A real 2/4 bar in a 4/4 song: the grid keeps 4/4 (known limitation: the bar
    starts are right up to the short bar; the user can move them after it)."""
    first, _ = grid(100, 4, 12)
    short = [first[-1] + 0.6, first[-1] + 1.2]
    rest, _ = grid(100, 4, 12, start=short[-1] + 0.6)
    beats = first + short + rest
    downbeats = [*first[::4], short[0], *rest[::4]]
    result = decode_beats(*network_output(beats, downbeats, rest[-1] + 2))
    assert set(bar_lengths(result)) == {4}
    assert np.allclose(result.downbeats[:12], downbeats[:12], atol=0.005)


def test_bar_starts_given_by_the_user_fix_the_bars_after_a_short_bar() -> None:
    first, _ = grid(100, 4, 12)
    short = [first[-1] + 0.6, first[-1] + 1.2]
    rest, _ = grid(100, 4, 12, start=short[-1] + 0.6)
    beats = first + short + rest
    downbeats = [*first[::4], short[0], *rest[::4]]
    output = network_output(beats, downbeats, rest[-1] + 2)
    result = decode_beats(*output, DecodingOptions(bar_starts=(rest[0] + 0.02,)))
    # before the given bar start, the bars are as detected; from it on, counted from it
    assert np.allclose(result.downbeats[:12], downbeats[:12], atol=0.005)
    # (the first beat after the short bar can be off: the decoder kept 4/4 there)
    assert np.allclose(result.downbeats[-11:], rest[4::4], atol=0.005)
    assert result.beats_per_bar == 4


def test_place_bar_starts_counts_from_each_given_start() -> None:
    beats, downbeats = grid(120, 4, 6)
    decoded = decode_beats(*network_output(beats, downbeats, 14))
    moved = place_bar_starts(decoded, [beats[2], beats[13]])
    assert np.allclose(moved.downbeats, [beats[i] for i in (0, 2, 6, 10, 13, 17, 21)], atol=0.005)
    assert place_bar_starts(decoded, []) is decoded


def test_a_one_beat_bar_before_a_given_bar_start_joins_the_bar_before() -> None:
    beats, downbeats = grid(120, 4, 6)
    decoded = decode_beats(*network_output(beats, downbeats, 14))
    later = place_bar_starts(decoded, [beats[5]])  # one beat after the bar start at beat 4
    assert np.allclose(later.downbeats, [beats[i] for i in (0, 5, 9, 13, 17, 21)], atol=0.005)
    pickup = place_bar_starts(decoded, [beats[1]])  # the first beat becomes a pickup
    assert np.allclose(pickup.downbeats, [beats[i] for i in (1, 5, 9, 13, 17, 21)], atol=0.005)


def test_beats_per_bar_can_be_set() -> None:
    beats, downbeats = grid(120, 4, 16)
    result = decode_beats(*network_output(beats, downbeats, 35), DecodingOptions(beats_per_bar=3))
    assert set(bar_lengths(result)) == {3}


def test_tempo_hint_picks_the_tempo_octave() -> None:
    beats, downbeats = grid(90, 4, 16)
    result = decode_beats(*network_output(beats, downbeats, 45), DecodingOptions(tempo_bpm=180))
    assert np.median(np.diff(result.beats)) == pytest.approx(60 / 180, abs=0.01)


def test_silence_gives_no_beats() -> None:
    beat, bar = network_output([], [], 10)
    result = decode_beats(beat, bar)
    assert len(result.beats) == 0
    assert result.beats_per_bar is None


def test_very_long_input_uses_fewer_meters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Above the memory budget only 3 and 4 beats per bar are tried."""
    monkeypatch.setattr("music_trainer.services.beat_decoding.MAX_POINTER_BYTES", 1)
    beats, downbeats = grid(110, 5, 12)
    result = decode_beats(*network_output(beats, downbeats, len(beats) * 60 / 110 + 2))
    assert result.beats_per_bar in (3, 4)
    forced = decode_beats(
        *network_output(beats, downbeats, len(beats) * 60 / 110 + 2),
        DecodingOptions(beats_per_bar=5),
    )
    assert forced.beats_per_bar == 5
