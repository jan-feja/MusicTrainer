"""Beat grid decoding on synthetic network outputs (no model needed)."""

import numpy as np
import pytest

from music_trainer.services.beat_decoding import (
    DecodingOptions,
    GridSection,
    decode_beats,
    fit_steady_tempo,
    place_bar_starts,
)
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


def sections(bpm: float, meters: list[tuple[int, int]], start: float = 1.0):
    """Beats and bar starts of consecutive sections: (beats per bar, bars) each."""
    beats, downbeats = [], []
    t = start
    for per_bar, bars in meters:
        for _ in range(bars):
            downbeats.append(t)
            for _ in range(per_bar):
                beats.append(t)
                t += 60 / bpm
    return beats, downbeats


def test_the_meter_can_change_between_sections() -> None:
    """A verse in 3/4 and a chorus in 4/4: every bar is found.

    (With 8-bar verses the grid would stay in 4/4 here: two meter changes cost more
    than the few wrong bar starts that 4/4 bars give in a 3/4 verse.)
    """
    plan = [(4, 4), (3, 12), (4, 8), (3, 12), (4, 6)]
    beats, downbeats = sections(120, plan)
    result = decode_beats(*network_output(beats, downbeats, beats[-1] + 2))
    assert bar_lengths(result) == [4] * 4 + [3] * 12 + [4] * 8 + [3] * 12 + [4] * 5
    assert np.max(np.abs(result.downbeats - downbeats)) < 0.005
    assert result.beats_per_bar == 3  # most bars


def test_a_few_odd_bars_do_not_make_a_section() -> None:
    """Two 3/4 bars in a 4/4 song are shorter than a section: the grid stays in 4/4."""
    beats, downbeats = sections(120, [(4, 12), (3, 2), (4, 12)])
    result = decode_beats(*network_output(beats, downbeats, beats[-1] + 2))
    assert set(bar_lengths(result)) == {4}


def test_a_real_tempo_change_is_followed() -> None:
    """80 BPM, then 140 BPM: not a tempo octave, so the grid follows the change."""
    slow, slow_bars = grid(80, 4, 8)
    fast, fast_bars = grid(140, 4, 12, start=slow[-1] + 60 / 80)
    result = decode_beats(*network_output(slow + fast, slow_bars + fast_bars, fast[-1] + 2))
    found = result.beats[result.beats > slow[0] + 0.1]  # (the very first beat may be missed)
    assert len(found) == len(slow) + len(fast) - 1
    assert np.max(np.abs(found - (slow + fast)[1:])) < 0.01
    bar_starts = result.downbeats[result.downbeats > slow[0] + 0.1]
    assert np.max(np.abs(bar_starts - (slow_bars + fast_bars)[1:])) < 0.01


def test_a_bar_start_given_in_one_section_leaves_the_next_section_alone() -> None:
    beats, downbeats = sections(120, [(3, 8), (4, 8)])
    decoded = decode_beats(*network_output(beats, downbeats, beats[-1] + 2))
    moved = place_bar_starts(decoded, [beats[7]])  # one beat after the third 3/4 bar start
    # the 3/4 bars are counted from there to the end of the section, the 4/4 bars stay
    expected = [beats[i] for i in (0, 3, 7, 10, 13, 16, 19, 22)] + downbeats[8:]
    assert np.allclose(moved.downbeats, expected, atol=0.005)


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


def test_steady_tempo_makes_beats_evenly_spaced() -> None:
    beats, _ = grid(75.5, 4, 20)
    jittered = [b + 0.015 * ((i * 7) % 3 - 1) for i, b in enumerate(beats)]
    decoded = decode_beats(*network_output(jittered, jittered[::4], 66))
    steady = fit_steady_tempo(decoded)
    assert np.allclose(np.diff(steady.beats), 60 / 75.5, atol=0.002)
    assert np.allclose(np.diff(steady.downbeats), 4 * 60 / 75.5, atol=0.005)


def test_beats_per_bar_can_be_set() -> None:
    beats, downbeats = grid(120, 4, 16)
    result = decode_beats(*network_output(beats, downbeats, 35), DecodingOptions(beats_per_bar=3))
    assert set(bar_lengths(result)) == {3}


def test_tempo_hint_picks_the_tempo_octave() -> None:
    beats, downbeats = grid(90, 4, 16)
    result = decode_beats(*network_output(beats, downbeats, 45), DecodingOptions(tempo_bpm=180))
    assert np.median(np.diff(result.beats)) == pytest.approx(60 / 180, abs=0.01)


def test_a_click_track_gets_four_beats_per_bar() -> None:
    """Every click looks like a bar start: there is no meter, so the decoder uses 4."""
    beats, _ = grid(100, 4, 20)
    result = decode_beats(*network_output(beats, beats, 50))
    assert result.beats_per_bar == 4
    assert result.info["meter"] == "default"
    assert len(result.beats) == len(beats)


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


# --- the user's sections --------------------------------------------------------------------


def pneuma_like() -> tuple[list[float], list[float], float, float]:
    """4 bars of 4/4 at 120 BPM, a verse of 4 x (6+6+5+6+5+5) eighths, 6 bars of 4/4."""
    beats, downbeats = sections(120, [(4, 4)])
    t = beats[-1] + 0.5
    verse_start = t
    for _ in range(4):
        for length in (6, 6, 5, 6, 5, 5):
            downbeats.append(t)
            for _ in range(length):
                beats.append(t)
                t += 0.25
    chorus, chorus_bars = sections(120, [(4, 6)], start=t)
    return beats + chorus, downbeats + chorus_bars, verse_start, chorus_bars[0]


def test_a_section_with_a_bar_pattern_and_its_own_tempo() -> None:
    beats, downbeats, verse, chorus = pneuma_like()
    output = network_output(beats, downbeats, beats[-1] + 2)
    options = DecodingOptions(
        sections=(
            GridSection(verse, pattern=(6, 6, 5, 6, 5, 5), tempo_bpm=240),
            GridSection(chorus, tempo_bpm=120),
        )
    )
    result = decode_beats(*output, options)
    verse_bars = [d for d in downbeats if verse - 0.1 < d]
    assert bar_lengths(result)[-len(verse_bars) + 1 :] == [6, 6, 5, 6, 5, 5] * 4 + [4] * 5
    # (the chorus's first bar start can be ~20 ms off: beats are smoothed across the tempo change)
    assert np.allclose(result.downbeats[-len(verse_bars) :], verse_bars, atol=0.025)


def test_a_section_with_a_given_meter_can_be_short() -> None:
    """Four 3/4 bars are too few for an automatic meter change; a section says so."""
    beats, downbeats = sections(120, [(4, 8), (3, 4), (4, 8)])
    output = network_output(beats, downbeats, beats[-1] + 2)
    assert set(bar_lengths(decode_beats(*output))) == {4}
    options = DecodingOptions(
        sections=(GridSection(downbeats[8], beats_per_bar=3), GridSection(downbeats[12]))
    )
    result = decode_beats(*output, options)
    assert bar_lengths(result) == [4] * 8 + [3] * 4 + [4] * 7
    assert np.allclose(result.downbeats, downbeats, atol=0.005)


def test_a_section_start_is_a_bar_start() -> None:
    """After a 2/4 bar the decoder keeps counting 4/4; a section from the next bar fixes it."""
    beats, downbeats = sections(100, [(4, 12), (2, 1), (4, 12)])
    output = network_output(beats, downbeats, beats[-1] + 2)
    result = decode_beats(*output, DecodingOptions(sections=(GridSection(downbeats[13]),)))
    # the beats are decoded again under the hint: no beats bent around the 2/4 bar
    assert np.allclose(result.downbeats, downbeats, atol=0.01)
    assert np.allclose(result.beats, beats, atol=0.01)
    assert result.info["guided"]


def test_a_bar_start_in_a_pattern_section_continues_the_pattern() -> None:
    beats, downbeats = sections(120, [(3, 2), (2, 1), (3, 2), (2, 1), (3, 2), (2, 1)])
    output = network_output(beats, downbeats, beats[-1] + 2)
    pattern = GridSection(beats[0], pattern=(3, 3, 2))
    decoded = decode_beats(*output, DecodingOptions(sections=(pattern,)))
    assert bar_lengths(decoded) == [3, 3, 2, 3, 3, 2, 3, 3]
    # the user says a bar starts on beat 9: it does, and the pattern goes on after it
    moved = decode_beats(*output, DecodingOptions(sections=(pattern,), bar_starts=(beats[9],)))
    assert np.isclose(moved.downbeats, beats[9], atol=0.01).any()
    after = bar_lengths(moved)[4:]
    assert after == [2, 3, 3, 2, 3]  # the pattern, in the phase the music has


def test_grid_section_bar_lengths() -> None:
    assert GridSection(0, pattern=(6, 5)).bar_length(3) == 5
    assert GridSection(0, beats_per_bar=7).bar_length(10) == 7
    assert GridSection(0).bar_length(0) is None
