"""Meter and tempo changes: decoder variants on the backend's beat grid regression set.

The regression set (backend/tests/data/beat_grids, from make_beat_regression_set.py) holds the
Beat This! output and the true beats and bars of 226 songs in four groups: steady (one meter,
steady tempo), tempo (the tempo changes), meter (bars of different lengths) and library (checks
only). Every variant decodes all of them; what counts is that the meter and tempo groups get
better while the steady group, and every song that was right, stays as it was.

Variants (patched into backend/src/music_trainer/services/beat_decoding.py):
  old               one meter per song, tempo octave conflict at a spread of 1.6 (decoder 1)
  sections_<cost>   the meter may change between sections of at least 4 bars, at this cost
  octave_<spread>   the tempo octave is only enforced above this spread (real tempo changes below)
  app               the app now: sections (cost 50, 3-8 beats per bar) + octave 1.95
  odd_<cost>[_check]  app + single bars of another length at this cost; _check: an odd bar is kept
                    only if the bars after it consistently prefer the new bar start (it still
                    breaks a swing song the network is confidently wrong on for a few bars)

Usage: python test_meter_sections.py            (writes results/meter_sections.json)
"""

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from common import save_result

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]

from music_trainer.services import beat_decoding as bd  # noqa: E402
from tests import beat_regression as br  # noqa: E402

APP = {"METER_CHANGE_COST": 50.0, "MIN_SECTION_BARS": 4, "SECTION_METERS": (3, 4, 5, 6, 7, 8), "OCTAVE_CONFLICT": 1.95}
OLD = APP | {"METER_CHANGE_COST": np.inf, "OCTAVE_CONFLICT": 1.6}
VARIANTS: dict[str, dict] = {
    "old": OLD,
    "sections_30": OLD | {"METER_CHANGE_COST": 30.0},
    "sections_40": OLD | {"METER_CHANGE_COST": 40.0},
    "sections_50": OLD | {"METER_CHANGE_COST": 50.0},
    "sections_60": OLD | {"METER_CHANGE_COST": 60.0},
    "sections_50_meters_3-7": OLD | {"METER_CHANGE_COST": 50.0, "SECTION_METERS": (3, 4, 5, 6, 7)},
    "sections_50_meters_2-7": OLD | {"METER_CHANGE_COST": 50.0, "SECTION_METERS": (2, 3, 4, 5, 6, 7)},
    "octave_1.95": OLD | {"OCTAVE_CONFLICT": 1.95},
    "octave_2.2": OLD | {"OCTAVE_CONFLICT": 2.2},
    "app": APP,
    "odd_20": APP | {"odd": (20.0, False)},
    "odd_10_check": APP | {"odd": (10.0, True)},
}
CHECK_BARS, CHECK_SHARE, CHECK_MEDIAN, CHECK_ROUNDS = 8, 0.85, 12.0, 6
ODD_LENGTHS = (1, 2, 3, 4, 5, 6, 7)
_ORIGINAL_SECTIONS = bd._meter_sections


# --- single odd bars (not in the app) ----------------------------------------------------------


def sections_with_odd_bars(evidence: np.ndarray, odd_cost: float, check: bool) -> np.ndarray:
    forbidden = np.zeros(len(evidence), dtype=bool)
    for _ in range(CHECK_ROUNDS if check else 1):
        labels = _odd_bar_viterbi(evidence, odd_cost, forbidden)
        rejected = _unconfirmed_odd_bars(evidence, labels) if check else []
        if not rejected:
            break
        for start, length in rejected:
            forbidden[max(0, start - length) : start + 2 * length] = True
    return labels


def _unconfirmed_odd_bars(evidence: np.ndarray, labels: np.ndarray) -> list[tuple[int, int]]:
    """Odd bars (between two bars of another, equal length) the bars after them do not confirm."""
    starts = np.flatnonzero(labels == 0)
    out = []
    for j in range(1, len(starts) - 2):
        s0, s1 = starts[j], starts[j + 1]
        before, odd, after = s0 - starts[j - 1], s1 - s0, starts[j + 2] - s1
        if odd == before or after != before:
            continue
        k = j + 1  # bars of the meter after the odd bar, up to the next change
        while k + 1 < len(starts) and starts[k + 1] - starts[k] == before and k - j < CHECK_BARS:
            k += 1
        new = starts[j + 1 : k + 1]
        old = new - odd + before  # the bar starts without the odd bar
        keep = (old >= 0) & (old < len(evidence))
        new, old = new[keep], old[keep]
        d = evidence[new] - evidence[old]
        if len(new) < 2 or np.mean(d > 0) < CHECK_SHARE or np.median(d) < CHECK_MEDIAN:
            out.append((int(s0), int(before)))
    return out


def _odd_bar_viterbi(evidence: np.ndarray, odd_cost: float, forbidden: np.ndarray) -> np.ndarray:
    """_meter_sections with one more kind of state: one bar of another length inside a meter."""
    full = bd.MIN_SECTION_BARS - 1
    states = [(0, m, c, q, m) for m in bd.SECTION_METERS for c in range(full + 1) for q in range(m)]
    states += [(1, m, n, q, n) for m in bd.SECTION_METERS for n in ODD_LENGTHS if n != m for q in range(n)]
    index = {s[:4]: i for i, s in enumerate(states)}
    kind, meter, count = (np.array([s[i] for s in states]) for i in range(3))
    beat, length = np.array([s[3] for s in states]), np.array([s[4] for s in states])
    inner = np.flatnonzero(beat > 0)
    inner_previous = np.array([index[(s[0], s[1], s[2], s[3] - 1)] for s in (states[i] for i in inner)])
    starts, ends = np.flatnonzero(beat == 0), np.flatnonzero(beat == length - 1)
    transition = np.full((len(ends), len(starts)), -np.inf)
    for a, e in enumerate(ends):
        ke, me, ce = kind[e], meter[e], count[e]
        for b, s in enumerate(starts):
            ks, ms, cs = kind[s], meter[s], count[s]
            cost = None
            if ke == 0 and ks == 0 and ms == me and cs == min(full, ce + 1):
                cost = 0.0
            elif ke == 0 and ks == 0 and ms != me and ce == full and cs == 0:
                cost = bd.METER_CHANGE_COST
            elif ke == 0 and ks == 1 and ms == me and ce == full:
                cost = odd_cost
            elif ke == 1 and ks == 0 and ms == me and cs == full:
                cost = 0.0
            if cost is not None:
                transition[a, b] = -cost - (bd.UNUSUAL_METER_COST if ks == 0 and ms >= 5 else 0.0)
    no_odd = np.where(kind[starts][None, :] == 1, -np.inf, transition)
    score = np.where((kind == 0) & (count == 0), np.where(beat == 0, evidence[0], 0.0), -np.inf)
    back = np.zeros((len(evidence), len(starts)), dtype=np.int32)
    columns = np.arange(len(starts))
    for i in range(1, len(evidence)):
        new = np.empty_like(score)
        new[inner] = score[inner_previous]
        candidates = score[ends][:, None] + (no_odd if forbidden[i] else transition)
        best = candidates.argmax(axis=0)
        new[starts] = candidates[best, columns] + evidence[i]
        back[i] = best
        score = new
    state, labels = int(score.argmax()), np.empty(len(evidence), dtype=int)
    start_column = {s: k for k, s in enumerate(starts)}
    for i in range(len(evidence) - 1, -1, -1):
        labels[i] = beat[state]
        if i == 0:
            break
        state = (int(inner_previous[np.searchsorted(inner, state)]) if beat[state] > 0
                 else int(ends[back[i, start_column[state]]]))
    return labels


# --- running ----------------------------------------------------------------------------------


def decode(job: tuple[str, str]) -> tuple[str, str, dict]:
    variant, song_id = job
    settings = dict(VARIANTS[variant])
    odd = settings.pop("odd", None)
    for name, value in settings.items():
        setattr(bd, name, value)
    bd._meter_sections = (_ORIGINAL_SECTIONS if odd is None
                          else lambda evidence: sections_with_odd_bars(evidence, *odd))
    _, row = br.decode_song(song_id)
    return variant, song_id, row


def main() -> None:
    songs = br.load_manifest()
    jobs = [(variant, song.id) for variant in VARIANTS for song in songs]
    rows: dict[str, dict[str, dict]] = {variant: {} for variant in VARIANTS}
    with ProcessPoolExecutor(min(12, os.cpu_count() or 1)) as pool:
        for variant, song_id, row in pool.map(decode, jobs, chunksize=8):
            rows[variant][song_id] = row
    old = rows["old"]
    summary = {}
    for variant, result in rows.items():
        means = br.group_means(songs, result)
        changed = {
            s.id: [old[s.id]["bar_F"], result[s.id]["bar_F"]]
            for s in songs
            if "bar_F" in result[s.id] and abs(result[s.id]["bar_F"] - old[s.id]["bar_F"]) >= 0.05
        }
        broke = [i for i, (a, b) in changed.items() if a >= 0.9 and b < a - 0.05]
        summary[variant] = {"groups": means, "better": sum(b > a for a, b in changed.values()),
                            "worse": sum(b < a for a, b in changed.values()), "broke": broke, "changed": changed}
        cells = "  ".join(f"{g} barF {v['bar_F']:.3f} l4 {v['loop_4bar']:.3f}" for g, v in means.items())
        print(f"{variant:24s} {cells}  better {summary[variant]['better']} worse {summary[variant]['worse']} "
              f"broke {broke}", flush=True)
    save_result("meter_sections", summary)


if __name__ == "__main__":
    main()
