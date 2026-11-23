"""Download SALAMI's Internet Archive recordings that have function labels (a seeded random subset).

SALAMI (github.com/DDMAL/salami-data-public) lists an archive.org URL per song; the original
*_vbr.mp3 derivatives are gone, so the item's metadata (archive.org/metadata/<item>) is asked for
the current MP3 (else Ogg) of the same track. Error pages served instead of audio are rejected.

Usage: python get_salami.py <MT_DATA>/salami <count>
  expects <MT_DATA>/salami/salami-data-public (the annotations repository); writes audio/<id>.mp3
"""

import csv
import json
import random
import subprocess
import sys
import urllib.request
from pathlib import Path


def main() -> None:
    root, count = Path(sys.argv[1]), int(sys.argv[2])
    repo = root / "salami-data-public"
    rows = [r for r in csv.DictReader(open(repo / "metadata" / "id_index_internetarchive.csv", encoding="utf8", errors="replace"))
            if (repo / "annotations" / r["SONG_ID"] / "parsed" / "textfile1_functions.txt").exists()]
    random.Random(0).shuffle(rows)
    out = root / "audio"
    out.mkdir(exist_ok=True)
    got = 0
    for r in rows:
        if got >= count:
            break
        target = out / f"{r['SONG_ID']}.mp3"
        if not target.exists():
            parts = r["URL"].split("/download/")[1].split("/")
            item, name = parts[0], parts[-1]
            base = name.replace("_vbr.mp3", "").replace(".mp3", "")
            try:
                meta = json.load(urllib.request.urlopen(f"https://archive.org/metadata/{item}", timeout=60))
            except Exception as error:  # network errors, removed items
                print("failed", r["SONG_ID"], error, flush=True)
                continue
            files = [f["name"] for f in meta.get("files", []) if f["name"].rsplit(".", 1)[0] == base]
            pick = next((f for f in files if f.endswith(".mp3")), None) or next((f for f in files if f.endswith(".ogg")), None)
            if not pick:
                print("failed", r["SONG_ID"], "no file", flush=True)
                continue
            result = subprocess.run(["curl", "-sSL", "--max-time", "180", "-o", str(target),
                                     f"https://archive.org/download/{item}/{pick}"], capture_output=True)
            head = target.read_bytes()[:64] if target.exists() else b""
            if result.returncode != 0 or target.stat().st_size < 100_000 or head.lstrip().startswith(b"<"):
                target.unlink(missing_ok=True)
                print("failed", r["SONG_ID"], "download", flush=True)
                continue
        got += 1
        print("ok", got, r["SONG_ID"], flush=True)


if __name__ == "__main__":
    main()
