"""Write the backend's beat grid regression set (backend/tests/data/beat_grids/).

For every chosen test song: the Beat This! final0 logits (the decoder's input, as int8 steps of
0.25) and the true beats and bar starts, in one songs.npz, plus manifest.json describing each
song. The backend test (tests/test_beat_regression.py) decodes them all and compares the result
with its baseline, without audio or the network.

Songs, by group:
  steady   one meter, steady tempo: score songs (basic set), the 8 steady Harmonix songs and 10 GTZAN
           clips per genre (chosen at random with a fixed seed)
  tempo    one meter, the tempo changes: score songs with tempo jumps, ramps and rubato, Harmonix
           songs from get_harmonix_changes.py
  meter    bars of different lengths: score songs with odd bars, sections in another meter and bar
           cycles, Harmonix songs from get_harmonix_changes.py, GTZAN clips whose bars vary
  library  songs from the app library without answers: checks only (beats per bar, tempo)

Usage: python make_beat_regression_set.py   (MT_DATA with the test sets and cached activations)
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from common import DATA
from test_beat_tracking import LIBRARY, Item, activations, load_items

OUT = Path(__file__).resolve().parents[1] / "backend" / "tests" / "data" / "beat_grids"
LOGIT_STEP = 0.25
GTZAN_PER_GENRE = 10
# app library songs with a known grid: video id -> title and checks (beats per bar, tempo and, for
# songs in one steady tempo, how far the beat intervals may spread: 95th / 5th percentile)
LIBRARY_SONGS = {
    "GG9m0jA8tdc": ("Joe Satriani - Cryin'", {"beats_per_bar": 4, "bpm": 75.5, "max_tempo_spread": 1.1}),
    "wNvOUkRTkz8": ("Red Hot Chili Peppers - Charlie", {"beats_per_bar": 4, "bpm": 111.3}),
    "IGMabBGydC0": ("Rusted Root - Send Me On My Way", {"beats_per_bar": 4, "bpm": 122.2, "max_tempo_spread": 1.15}),
}


def quantize(logits: np.ndarray) -> np.ndarray:
    return np.clip(np.round(np.asarray(logits, dtype=np.float64) / LOGIT_STEP), -128, 127).astype(np.int8)


def bars_vary(item: Item) -> bool:
    lengths = np.diff(np.searchsorted(item.beats, item.downbeats - 1e-6))
    return len(lengths) > 2 and Counter(lengths.tolist()).most_common(1)[0][1] / len(lengths) < 0.9


def group_of(item: Item) -> str:
    if item.set in ("score", "score_changes"):
        if item.category == "tempo changes":
            return "tempo"
        if item.category in ("odd bars", "meter sections", "meter patterns"):
            return "meter"
        return "steady"
    if item.set == "harmonix_changes":
        return "tempo" if item.category == "tempo changes" else "meter"
    return "meter" if bars_vary(item) else "steady"


def main() -> None:
    items = [i for i in load_items(("score", "score_changes", "harmonix", "harmonix_changes")) if i.name != "bass"]
    rng = np.random.default_rng(0)
    gtzan = load_items(("gtzan",))
    for genre in sorted({i.category for i in gtzan}):
        clips = [i for i in gtzan if i.category == genre]
        items += [clips[k] for k in sorted(rng.choice(len(clips), GTZAN_PER_GENRE, replace=False))]

    titles = {}
    for listing in ("selection.json", "changes.json"):
        path = Path(DATA, "harmonix", listing)
        if path.exists():
            titles |= {s["file"]: f"{s['artist']} - {s['title']}" for s in json.loads(path.read_text(encoding="utf-8"))}
    arrays: dict[str, np.ndarray] = {}
    manifest = []
    for item in items:
        song_id = f"{item.set}/{item.name}"
        beat, down = activations(item)
        arrays[f"{song_id}/beat"], arrays[f"{song_id}/downbeat"] = quantize(beat), quantize(down)
        arrays[f"{song_id}/beats"] = item.beats.astype(np.float32)
        arrays[f"{song_id}/downbeats"] = item.downbeats.astype(np.float32)
        source = {"score": "score song", "score_changes": "score song", "gtzan": "GTZAN",
                  "harmonix": "Harmonix Set", "harmonix_changes": "Harmonix Set"}[item.set]
        manifest.append({"id": song_id, "group": group_of(item), "category": item.category, "source": source,
                         "title": titles.get(item.name, "")})
    for video_id, (title, checks) in LIBRARY_SONGS.items():
        stored = np.load(LIBRARY / video_id / "beat_activations.npz")
        song_id = f"library/{video_id}"
        arrays[f"{song_id}/beat"], arrays[f"{song_id}/downbeat"] = quantize(stored["beat"]), quantize(stored["downbeat"])
        manifest.append({"id": song_id, "group": "library", "category": "real (no answers)", "source": "app library",
                         "title": title, "checks": checks})

    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "songs.npz", **arrays)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = Counter(m["group"] for m in manifest)
    print(f"{len(manifest)} songs {dict(counts)}, {(OUT / 'songs.npz').stat().st_size / 1e6:.1f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
