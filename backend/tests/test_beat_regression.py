"""Regression test of beat and bar decoding on real and score songs.

Slow (a few hundred songs), so not part of the default run:
    pytest -m beat_regression -s                          # -s prints the comparison
    UPDATE_BEAT_BASELINE=1 pytest -m beat_regression -s   # accept the results as the baseline

Every song is decoded from its stored network output and compared with its true beats and bar
starts; the numbers must not fall below the stored baseline (tests/data/beat_grids/baseline.json).
"""

import json
import os

import numpy as np
import pytest

from tests.beat_regression import (
    BASELINE_FILE,
    METRICS,
    Song,
    decode_all,
    group_means,
    load_manifest,
    report,
)

pytestmark = pytest.mark.beat_regression

GROUP_TOLERANCE = 0.005  # a group's mean may drop this much (rounding, ties)
WORKING = 0.9  # songs with at least this bar F-measure in the baseline ...
SONG_TOLERANCE = 0.05  # ... must stay within this of it
BPM_TOLERANCE = 0.02  # library songs: tempo within 2 % of the known one
MAX_ODD_BARS = 0.02  # library songs: share of bars with another number of beats


@pytest.fixture(scope="module")
def decoded() -> tuple[list[Song], dict[str, dict], dict[str, dict]]:
    songs = load_manifest()
    rows = decode_all(songs)
    if os.environ.get("UPDATE_BEAT_BASELINE") == "1":
        BASELINE_FILE.write_text(json.dumps({"songs": rows}, indent=1, sort_keys=True) + "\n")
    baseline = json.loads(BASELINE_FILE.read_text())["songs"]
    print("\n" + report(songs, rows, baseline))
    return songs, rows, baseline


def test_every_song_is_in_the_baseline(decoded) -> None:
    songs, _, baseline = decoded
    missing = [song.id for song in songs if song.id not in baseline]
    assert not missing, f"not in the baseline (run with UPDATE_BEAT_BASELINE=1): {missing}"


@pytest.mark.parametrize("group", ["steady", "tempo", "meter"])
def test_groups_do_not_get_worse(decoded, group: str) -> None:
    songs, rows, baseline = decoded
    now, before = group_means(songs, rows)[group], group_means(songs, baseline)[group]
    worse = {m: (before[m], now[m]) for m in METRICS if now[m] < before[m] - GROUP_TOLERANCE}
    assert not worse, f"{group}: worse than the baseline (before, now): {worse}"


def test_songs_that_worked_still_work(decoded) -> None:
    songs, rows, baseline = decoded
    broken = {
        song.id: (baseline[song.id]["bar_F"], rows[song.id]["bar_F"])
        for song in songs
        if "bar_F" in baseline.get(song.id, {})
        and baseline[song.id]["bar_F"] >= WORKING
        and rows[song.id]["bar_F"] < baseline[song.id]["bar_F"] - SONG_TOLERANCE
    }
    assert not broken, f"bar starts got worse (before, now): {broken}"


def test_library_songs_keep_their_grid(decoded) -> None:
    songs, rows, _ = decoded
    for song in (s for s in songs if s.group == "library"):
        row = rows[song.id]
        assert row["beats_per_bar"] == song.checks["beats_per_bar"], song.id
        assert row["odd_bars"] <= MAX_ODD_BARS, song.id
        assert np.isclose(row["bpm"], song.checks["bpm"], rtol=BPM_TOLERANCE), song.id
        if "max_tempo_spread" in song.checks:  # no double-time stretch (Cryin' at 4:27)
            assert row["tempo_spread"] <= song.checks["max_tempo_spread"], song.id
