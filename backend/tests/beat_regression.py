"""Beat grid regression set: stored network outputs of test songs, their true beats and bars.

tests/data/beat_grids/ holds, for every song, the Beat This! output (logits at 50 fps, so no
audio and no model are needed) and the true beats and bar starts. Decoding all of them shows
whether a change to the decoder helps or hurts, song by song. See README.md there.
"""

import json
import os
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from music_trainer.services.beat_decoding import DecodingOptions, decode_beats

DATA_DIR = Path(__file__).parent / "data" / "beat_grids"
SONGS_FILE = DATA_DIR / "songs.npz"
MANIFEST_FILE = DATA_DIR / "manifest.json"
BASELINE_FILE = DATA_DIR / "baseline.json"
LOGIT_STEP = 0.25  # logits are stored as int8 multiples of this (range -32 .. 31.75)
TOLERANCE = 0.07  # seconds: a detected beat this close to a true one is right
METRICS = ("beat_F", "bar_F", "loop_1bar", "loop_4bar")


@dataclass(frozen=True)
class Song:
    id: str
    group: str
    """'steady': one meter and a steady tempo; 'tempo': the tempo changes; 'meter': bars of
    different lengths; 'library': songs from the app library, no answers, only checks."""
    category: str
    source: str
    title: str = ""
    checks: dict = field(default_factory=dict)
    """For songs without answers: beats_per_bar and bpm the grid must have, and (for songs
    played in one tempo) max_tempo_spread, the tempo_spread it must stay under."""


def load_manifest() -> list[Song]:
    rows = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return [Song(**row) for row in rows]


_songs: np.lib.npyio.NpzFile | None = None


def song_arrays(song_id: str) -> dict[str, np.ndarray]:
    """Logits (float) and, for songs with answers, the true beats and bar starts (seconds)."""
    global _songs
    if _songs is None:
        _songs = np.load(SONGS_FILE)
    arrays = {
        "beat": _songs[f"{song_id}/beat"].astype(np.float64) * LOGIT_STEP,
        "downbeat": _songs[f"{song_id}/downbeat"].astype(np.float64) * LOGIT_STEP,
    }
    if f"{song_id}/beats" in _songs.files:
        arrays["beats"] = _songs[f"{song_id}/beats"].astype(np.float64)
        arrays["downbeats"] = _songs[f"{song_id}/downbeats"].astype(np.float64)
    return arrays


# --- metrics ---------------------------------------------------------------------------------


def f_measure(reference: np.ndarray, detected: np.ndarray) -> float:
    """F-measure of detected times against true ones, each matched at most once."""
    if len(reference) == 0 or len(detected) == 0:
        return float(len(reference) == len(detected))
    hits, j = 0, 0
    for t in reference:  # both sorted, true times far more than 2 * TOLERANCE apart
        while j < len(detected) and detected[j] < t - TOLERANCE:
            j += 1
        if j < len(detected) and abs(detected[j] - t) <= TOLERANCE:
            hits += 1
            j += 1
    precision, recall = hits / len(detected), hits / len(reference)
    return 0.0 if hits == 0 else 2 * precision * recall / (precision + recall)


def loop_accuracy(reference: np.ndarray, detected: np.ndarray, span: int) -> float:
    """Set A on a true point (snapped to the nearest detected one), step `span` detected points:
    how often is B the right true point too? Extra or missing bar starts make this fail."""
    if len(reference) <= span:
        return float("nan")
    if len(detected) == 0:
        return 0.0
    right = 0
    for k in range(len(reference) - span):
        i = int(np.argmin(np.abs(detected - reference[k])))
        right += (
            abs(detected[i] - reference[k]) < TOLERANCE
            and i + span < len(detected)
            and abs(detected[i + span] - reference[k + span]) < TOLERANCE
        )
    return right / (len(reference) - span)


def odd_bar_share(beats: np.ndarray, downbeats: np.ndarray) -> float:
    if len(downbeats) < 3:
        return float("nan")
    counts = np.bincount(np.diff(np.searchsorted(beats, downbeats - 1e-6)))
    return float(1 - counts.max() / counts.sum())


def evaluate(arrays: dict[str, np.ndarray], beats: np.ndarray, downbeats: np.ndarray) -> dict:
    row = {"odd_bars": round(odd_bar_share(beats, downbeats), 4)}
    intervals = np.diff(beats)
    row["bpm"] = round(float(60 / np.median(intervals)), 2) if len(beats) > 2 else 0.0
    # how far the tempo strays: 95th / 5th percentile of the beat intervals
    row["tempo_spread"] = (
        round(float(np.percentile(intervals, 95) / np.percentile(intervals, 5)), 3)
        if len(beats) > 4
        else 1.0
    )
    if "beats" not in arrays:
        return row
    ref_beats, ref_downbeats = arrays["beats"], arrays["downbeats"]
    # only the stretch with answers (some recordings are longer than the annotated part)
    lo, hi = ref_beats[0] - TOLERANCE, ref_beats[-1] + TOLERANCE
    beats = beats[(beats >= lo) & (beats <= hi)]
    downbeats = downbeats[(downbeats >= lo) & (downbeats <= hi)]
    row["beat_F"] = round(f_measure(ref_beats, beats), 4)
    row["bar_F"] = round(f_measure(ref_downbeats, downbeats), 4)
    row["loop_1bar"] = round(loop_accuracy(ref_downbeats, downbeats, 1), 4)
    row["loop_4bar"] = round(loop_accuracy(ref_downbeats, downbeats, 4), 4)
    return row


# --- decoding ---------------------------------------------------------------------------------


def decode_song(song_id: str) -> tuple[str, dict]:
    arrays = song_arrays(song_id)
    grid = decode_beats(arrays["beat"], arrays["downbeat"], DecodingOptions())
    row = evaluate(arrays, np.asarray(grid.beats), np.asarray(grid.downbeats))
    row["beats_per_bar"] = grid.beats_per_bar
    return song_id, row


def decode_all(songs: Iterable[Song], workers: int | None = None) -> dict[str, dict]:
    ids = [song.id for song in songs]
    workers = workers or min(8, os.cpu_count() or 1)
    if workers == 1:
        return dict(map(decode_song, ids))
    with ProcessPoolExecutor(workers) as pool:
        return dict(pool.map(decode_song, ids, chunksize=4))


def group_means(songs: list[Song], rows: dict[str, dict]) -> dict[str, dict[str, float]]:
    means: dict[str, dict[str, float]] = {}
    for group in sorted({song.group for song in songs if song.group != "library"}):
        members = [rows[song.id] for song in songs if song.group == group]
        means[group] = {
            m: round(float(np.nanmean([r[m] for r in members])), 4) for m in METRICS
        } | {"songs": len(members)}
    return means


def report(songs: list[Song], rows: dict[str, dict], baseline: dict[str, dict]) -> str:
    """Group means now vs. the baseline, and every song whose bar F-measure moved by 0.05+."""
    lines = [f"{'group':10s}{'songs':>6s}" + "".join(f"{m:>22s}" for m in METRICS)]
    now, before = group_means(songs, rows), group_means(songs, baseline)
    for group, values in now.items():
        cells = "".join(
            f"{before[group][m]:>10.3f} -> {values[m]:<9.3f}"
            if group in before
            else f"{values[m]:>22.3f}"
            for m in METRICS
        )
        lines.append(f"{group:10s}{values['songs']:>6d}{cells}")
    moved = [
        (rows[s.id]["bar_F"] - baseline[s.id]["bar_F"], s)
        for s in songs
        if s.id in baseline
        and "bar_F" in rows[s.id]
        and abs(rows[s.id]["bar_F"] - baseline[s.id]["bar_F"]) >= 0.05
    ]
    for _, song in sorted(moved, key=lambda m: m[0]):
        lines.append(
            f"  bar F {baseline[song.id]['bar_F']:.2f} -> {rows[song.id]['bar_F']:.2f}  "
            f"{song.group:7s} {song.id} ({song.category})"
        )
    return "\n".join(lines)
