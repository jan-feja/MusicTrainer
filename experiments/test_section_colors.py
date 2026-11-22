"""Do the grid editor's section colors change where sections start?

The editor colors the music by similarity (backend/src/music_trainer/services/visual.py:
timbre and harmony, smoothed, PCA, hue). On the Harmonix songs of the beat regression set
(YouTube audio that lines up with the annotations; see common.harmonix_warped), this measures how
much the color changes at the annotated section starts compared with anywhere else:

  change(t)     distance between the mean color of the 4 s after t and of the 4 s before t
  percentile    where the largest change within +-1 s of a section start ranks among the
                changes at all times of the song (50 % = no better than chance)
  top 20 %      share of section starts whose change is among the song's largest 20 %
  chance        the same for random times instead of section starts

Usage: python test_section_colors.py        (writes results/section_colors.json)
"""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from common import DATA, harmonix_offset, save_result

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from music_trainer.services.audio import decode_audio  # noqa: E402
from music_trainer.services.visual import SAMPLE_RATE, compute_picture  # noqa: E402

WINDOW = 4.0  # seconds on each side
TOLERANCE = 1.0  # seconds around a section start
SEGMENTS = Path(DATA, "harmonix_full", "harmonixset-main", "dataset", "segments")


def aligned_shift(song: str) -> float | None:
    """Seconds to add to annotation times for the YouTube audio (from the aligned beats)."""
    rows = np.loadtxt(Path(DATA, "harmonix", "ann", f"{song}.beats_and_downbeats.txt"))
    cache = Path(DATA, "harmonix", "aligned", f"{song}.json")
    data = json.loads(cache.read_text()) if cache.exists() else None
    if data is None:  # aligned by a constant shift instead
        return harmonix_offset(song, str(Path(DATA, "songs", f"{song}.wav")))
    beats, positions = np.array(data["beats"]), np.array(data["positions"])
    best = None
    for k in range(len(rows) - len(beats) + 1):
        if np.array_equal(rows[k : k + len(beats), 1].astype(int), positions):
            d = beats - rows[k : k + len(beats), 0]
            if best is None or np.std(d) < best[1]:
                best = (float(np.median(d)), float(np.std(d)))
    return None if best is None or best[1] > 0.5 else best[0]  # cut or warped songs: skip


def score(song: str) -> dict | None:
    wav = Path(DATA, "songs", f"{song}.wav")
    segments = SEGMENTS / f"{song}.txt"
    if not wav.exists() or not segments.exists():
        return None
    shift = aligned_shift(song)
    if shift is None:
        return None
    starts = np.array([float(line.split()[0]) for line in segments.read_text().splitlines() if line.strip()])
    picture = compute_picture(decode_audio(wav, SAMPLE_RATE))
    colors = picture.colors.astype(float)
    step = picture.color_step
    w = int(WINDOW / step)
    change = np.zeros(len(colors))
    for i in range(w, len(colors) - w):
        change[i] = np.linalg.norm(colors[i : i + w].mean(0) - colors[i - w : i].mean(0))
    valid = change[w : len(colors) - w]
    duration = len(colors) * step
    ranks, top = [], []
    for t in starts + shift:
        if t < WINDOW + TOLERANCE or t > duration - WINDOW - TOLERANCE:
            continue  # the song's first and last seconds have no window on both sides
        lo, hi = int((t - TOLERANCE) / step), int((t + TOLERANCE) / step) + 1
        peak = change[lo:hi].max()
        ranks.append(float(np.mean(valid < peak)))
        top.append(peak >= np.percentile(valid, 80))
    # chance level: the same +-1 s maximum at random times
    rng = np.random.default_rng(0)
    random_ranks, random_top = [], []
    for t in rng.uniform(WINDOW + TOLERANCE, duration - WINDOW - TOLERANCE, 200):
        lo, hi = int((t - TOLERANCE) / step), int((t + TOLERANCE) / step) + 1
        random_ranks.append(float(np.mean(valid < change[lo:hi].max())))
        random_top.append(change[lo:hi].max() >= np.percentile(valid, 80))
    return {"song": song, "starts": len(ranks), "percentile": float(np.mean(ranks)) if ranks else None,
            "top20": float(np.mean(top)) if top else None, "chance_percentile": float(np.mean(random_ranks)),
            "chance_top20": float(np.mean(random_top))}


def main() -> None:
    # the Harmonix songs of the beat regression set: those whose audio lines up with the annotations
    manifest = Path(__file__).resolve().parents[1] / "backend" / "tests" / "data" / "beat_grids" / "manifest.json"
    songs = sorted(row["id"].split("/")[1] for row in json.loads(manifest.read_text(encoding="utf-8"))
                   if row["source"] == "Harmonix Set")
    with ProcessPoolExecutor(min(8, os.cpu_count() or 1)) as pool:
        rows = [r for r in pool.map(score, songs) if r and r["starts"]]
    summary = {
        "songs": len(rows),
        "section_starts": int(sum(r["starts"] for r in rows)),
        "percentile": round(float(np.mean([r["percentile"] for r in rows])), 3),
        "top20": round(float(np.average([r["top20"] for r in rows], weights=[r["starts"] for r in rows])), 3),
        "chance_percentile": round(float(np.mean([r["chance_percentile"] for r in rows])), 3),
        "chance_top20": round(float(np.mean([r["chance_top20"] for r in rows])), 3),
    }
    print(summary)
    for r in rows:
        print(f"  {r['song']:32s} starts {r['starts']:3d}  percentile {r['percentile']:.2f}  top20 {r['top20']:.2f}")
    save_result("section_colors", {"summary": summary, "per_song": rows})


if __name__ == "__main__":
    main()
