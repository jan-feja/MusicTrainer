"""Harmonix Set songs whose meter or tempo changes: pick them, download their audio, copy annotations.

The Harmonix Set (github.com/urinieto/harmonixset) has human beat and bar annotations for 912
songs and a YouTube link for each. From the annotations alone this picks:
  meter  bars of another length make up at least 10 % of the song (sections in 3/4, 6/4 or 7/4,
         cycles like 7+7+7+8, single odd bars) - Rush "Limelight", Soundgarden "Fell On Black Days"
  tempo  one meter, but the local tempo (median of 8 beats) spans at least a factor of 1.15
         between its 5th and 95th percentile - accelerating metal songs, live recordings, songs
         with a slow intro
and only songs whose YouTube audio matched the annotated recording (Harmonix alignment score
>= 0.85). Dead links are skipped.

Writes MT_DATA/songs/<id>.wav, MT_DATA/harmonix/ann/<id>.beats_and_downbeats.txt and
MT_DATA/harmonix/changes.json (read by test_beat_tracking.py, set "harmonix_changes").

Usage: python get_harmonix_changes.py <harmonixset>/dataset
Needs yt-dlp (with Deno for YouTube) and ffmpeg on PATH.
"""

import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from common import DATA

MIN_ODD_BARS = 0.10
MIN_TEMPO_SPREAD = 1.15
MIN_ALIGNMENT = 0.85
ALREADY_USED = {"0038_bringmetolife", "0110_girlsandboys", "0222_realgoodlooking", "0343_banjo", "0362_crazygirl",
                "0380_everybodytalks", "0468_openarms", "0566_americanwoman", "0625_complicated",
                "0734_iftodaywasyourlastday"}  # the steady "harmonix" set


def describe(path: Path) -> dict | None:
    rows = np.loadtxt(path, ndmin=2)
    times, positions = rows[:, 0], rows[:, 1].astype(int)
    lengths = np.diff(np.flatnonzero(positions == 1))
    if len(lengths) < 8:
        return None
    counts = Counter(lengths.tolist())
    main, main_count = counts.most_common(1)[0]
    intervals = np.diff(times)
    local = np.array([60 / np.median(intervals[i : i + 8]) for i in range(len(intervals) - 8)])
    return {
        "bar_lengths": dict(sorted(counts.items())),
        "beats_per_bar": main,
        "odd_bars": round(1 - main_count / len(lengths), 3),
        "tempo_spread": round(float(np.percentile(local, 95) / np.percentile(local, 5)), 3),
        "bpm": round(float(60 / np.median(intervals)), 1),
    }


def main() -> None:
    root = Path(sys.argv[1])
    meta = {r["File"]: r for r in csv.DictReader(open(root / "metadata.csv", encoding="utf8"))}
    urls = {r["File"]: r["URL"] for r in csv.DictReader(open(root / "youtube_urls.csv"))}
    alignment = {r["File"]: float(r["score"]) for r in csv.DictReader(open(root / "youtube_alignment_scores.csv"))}
    songs_dir, ann_dir = Path(DATA, "songs"), Path(DATA, "harmonix", "ann")
    songs_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)
    chosen = []
    for path in sorted((root / "beats_and_downbeats").glob("*.txt")):
        song = path.stem
        info = describe(path)
        if info is None or song in ALREADY_USED or alignment.get(song, 0) < MIN_ALIGNMENT:
            continue
        if info["odd_bars"] >= MIN_ODD_BARS:
            kind = "meter changes"
        elif info["tempo_spread"] >= MIN_TEMPO_SPREAD and info["odd_bars"] < 0.08:
            kind = "tempo changes"
        else:
            continue
        wav = songs_dir / f"{song}.wav"
        if not wav.exists():
            result = subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio", "-x", "--audio-format", "wav",
                                     "-o", str(songs_dir / f"{song}.%(ext)s"), urls[song]], capture_output=True, text=True)
            if not wav.exists():
                print(f"skipped {song}: {result.stderr.strip()[-120:]}", flush=True)
                continue
        shutil.copy(path, ann_dir / f"{song}.beats_and_downbeats.txt")
        chosen.append({"file": song, "title": meta[song]["Title"], "artist": meta[song]["Artist"], "kind": kind,
                       "url": urls[song], "alignment": alignment[song], **info})
        print(f"{kind:14s} {song:30s} {info['bar_lengths']} spread {info['tempo_spread']}", flush=True)
    Path(DATA, "harmonix", "changes.json").write_text(json.dumps(chosen, indent=1, ensure_ascii=False))
    print(len(chosen), "songs")


if __name__ == "__main__":
    main()
