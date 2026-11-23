"""Strings and frets for transcribed notes: a fingering search, and a naive baseline.

A note can be played on several strings (E4 = 64: open high E, 5th fret B, 9th fret G, ...);
picking one is what turns notes into a tab. The search:
  1. groups notes that start together (within 35 ms) into chords;
  2. lists every way to play a chord: one note per string, frets 0..MAX_FRET;
  3. scores each way (hand span over 4 frets, high frets) and each move between consecutive
     chords (how far the hand moves along the neck), and keeps the cheapest path (Viterbi).
The baseline plays every note at its lowest possible fret.
"""

import itertools
from dataclasses import dataclass

import numpy as np

STANDARD = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4, low string first
BASS_STANDARD = (28, 33, 38, 43)  # E1 A1 D2 G2
MAX_FRET = 20
CHORD_WINDOW = 0.035

# costs (log-probability-like units)
SPAN_FREE = 4  # frets the hand covers without stretching
SPAN_COST = 3.0  # per fret of stretch beyond that
HEIGHT_COST = 0.15  # per fret of the hand's position (lower positions are more common)
MOVE_COST = 0.6  # per fret the hand moves between chords
MOVE_GAP = 0.3  # seconds: moves after a pause cost half
OPEN_BONUS = 0.4  # open strings are easy (and common in GuitarSet-style playing)


@dataclass(frozen=True)
class TabNote:
    onset: float
    offset: float
    pitch: int
    string: int  # 0 = lowest string
    fret: int


def positions(pitch: int, tuning=STANDARD, max_fret=MAX_FRET) -> list[tuple[int, int]]:
    """(string, fret) where `pitch` can be played."""
    return [(s, pitch - open_) for s, open_ in enumerate(tuning) if 0 <= pitch - open_ <= max_fret]


def group_chords(notes: list[tuple[float, float, int]], window: float = CHORD_WINDOW) -> list[list[int]]:
    """Indices of notes starting together, in time order."""
    order = sorted(range(len(notes)), key=lambda i: (notes[i][0], notes[i][2]))
    groups: list[list[int]] = []
    for i in order:
        if groups and notes[i][0] - notes[groups[-1][0]][0] <= window:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def _fingerings(pitches: list[int], tuning, max_fret) -> list[tuple[tuple[int, int], ...]]:
    options = [positions(p, tuning, max_fret) for p in pitches]
    if any(not o for o in options):  # unplayable notes (out of range) are dropped later
        options = [o or [(-1, -1)] for o in options]
    out = []
    for combo in itertools.product(*options):
        strings = [s for s, _ in combo if s >= 0]
        if len(strings) == len(set(strings)):
            out.append(combo)
        if len(out) > 400:
            break
    return out or [tuple(o[0] for o in options)]


def _shape_cost(combo) -> tuple[float, float]:
    """Cost of holding a fingering, and where the hand is (mean fretted fret)."""
    frets = [f for s, f in combo if s >= 0 and f > 0]
    opens = sum(1 for s, f in combo if s >= 0 and f == 0)
    if not frets:
        return -OPEN_BONUS * opens, 0.0
    span = max(frets) - min(frets)
    cost = SPAN_COST * max(0, span - SPAN_FREE + 1) + HEIGHT_COST * min(frets) - OPEN_BONUS * opens
    return cost, float(np.mean(frets))


def assign_frets(notes: list[tuple[float, float, int]], tuning=STANDARD, max_fret=MAX_FRET) -> list[TabNote]:
    """Strings and frets for (onset, offset, midi pitch) notes, by the fingering search."""
    if not notes:
        return []
    groups = group_chords(notes)
    options = [_fingerings([notes[i][2] for i in g], tuning, max_fret) for g in groups]
    shapes = [[_shape_cost(c) for c in opts] for opts in options]
    score = np.array([cost for cost, _ in shapes[0]])
    back = []
    for k in range(1, len(groups)):
        gap = notes[groups[k][0]][0] - max(notes[i][1] for i in groups[k - 1])
        move = MOVE_COST * (0.5 if gap > MOVE_GAP else 1.0)
        prev_pos = np.array([p for _, p in shapes[k - 1]])
        prev_fretted = np.array([p > 0 for _, p in shapes[k - 1]])
        new, ptr = [], []
        for cost, pos in shapes[k]:
            # moving from or to open strings only costs nothing
            trans = np.where(prev_fretted & (pos > 0), move * np.abs(prev_pos - pos), 0.0)
            total = score + trans
            j = int(np.argmin(total))
            new.append(total[j] + cost)
            ptr.append(j)
        score = np.array(new)
        back.append(ptr)
    choice = [int(np.argmin(score))]
    for ptr in reversed(back):
        choice.append(ptr[choice[-1]])
    choice.reverse()
    out = []
    for g, opts, c in zip(groups, options, choice):
        for i, (s, f) in zip(g, opts[c]):
            if s >= 0:
                out.append(TabNote(notes[i][0], notes[i][1], notes[i][2], s, f))
    return sorted(out, key=lambda n: (n.onset, n.string))


def lowest_fret(notes: list[tuple[float, float, int]], tuning=STANDARD, max_fret=MAX_FRET) -> list[TabNote]:
    """Baseline: every note at its lowest fret (chord notes on distinct strings where possible)."""
    out = []
    for g in group_chords(notes):
        used = set()
        for i in sorted(g, key=lambda i: notes[i][2]):
            cands = sorted(positions(notes[i][2], tuning, max_fret), key=lambda sf: sf[1])
            pick = next((sf for sf in cands if sf[0] not in used), cands[0] if cands else None)
            if pick:
                used.add(pick[0])
                out.append(TabNote(notes[i][0], notes[i][1], notes[i][2], *pick))
    return sorted(out, key=lambda n: (n.onset, n.string))
