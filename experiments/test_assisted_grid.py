"""Assisted beat grids: how far do the user's sections and bar starts get the decoder?

On the backend's regression set (songs with true beats and bars), a simulated user describes
each song the way the app lets them:
  sections   where the bars change (a run of at least 4 bars of one length, or a repeating
             cycle like 4+4+4+3 or 6+6+5+6+5+5), they add a section with that meter or bar
             pattern, starting on the true bar start; where the true beats are twice or half
             as fast as the detected ones there (and the section keeps its tempo), they also
             give the section's tempo (2x / 1/2x)
  + taps     also a bar start right after every single odd bar (tapped or set with < Bar start >)
Both are compared with the automatic grid (no hints). The user's times are exact true bar
starts; the decoder snaps them to its nearest beat, as in the app.

The simulated user is backend/tests/beat_regression.py's simulated_hints (the regression test
checks the guided grids too). Usage: python test_assisted_grid.py   (writes results/assisted_grid.json)
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

def run(song_id: str) -> tuple[str, dict]:
    arrays = br.song_arrays(song_id)
    auto = bd.decode_beats(arrays["beat"], arrays["downbeat"])
    row = {"auto": br.evaluate(arrays, auto.beats, auto.downbeats)}
    for name, taps in (("sections", False), ("sections_taps", True)):
        sections, bar_starts = br.simulated_hints(arrays, auto, taps)
        grid = bd.decode_beats(arrays["beat"], arrays["downbeat"],
                               bd.DecodingOptions(sections=sections, bar_starts=bar_starts), automatic=auto)
        row[name] = br.evaluate(arrays, grid.beats, grid.downbeats)
        row[name]["hints"] = len(sections) + len(bar_starts)
    return song_id, row


def main() -> None:
    songs = [s for s in br.load_manifest() if s.group != "library"]
    with ProcessPoolExecutor(min(12, os.cpu_count() or 1)) as pool:
        rows = dict(pool.map(run, [s.id for s in songs], chunksize=4))
    summary = {}
    for group in ("steady", "tempo", "meter"):
        members = [s.id for s in songs if s.group == group]
        summary[group] = {
            method: {m: round(float(np.nanmean([rows[i][method][m] for i in members])), 3)
                     for m in ("beat_F", "bar_F", "loop_1bar", "loop_4bar")}
            | ({"hints per song": round(float(np.mean([rows[i][method]["hints"] for i in members])), 1)}
               if method != "auto" else {})
            for method in ("auto", "sections", "sections_taps")
        }
        print(group, summary[group], flush=True)
    worse = {i: (r["auto"]["bar_F"], r["sections_taps"]["bar_F"]) for i, r in rows.items()
             if r["sections_taps"]["bar_F"] < r["auto"]["bar_F"] - 0.05}
    print("worse with hints:", worse)
    save_result("assisted_grid", {"summary": summary, "worse_with_hints": worse, "per_song": rows})


if __name__ == "__main__":
    main()
