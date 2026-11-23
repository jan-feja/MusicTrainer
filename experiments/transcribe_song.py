"""A real song -> notes and tabs for every instrument (the whole pipeline, for a look at the result).

1. Beats and bar starts: Beat This! (as the app).
2. Notes per instrument: YourMT3+ on the mix (yourmt3_runner.py writes the MIDI first).
3. Parts: guitar, bass, keys (piano, organ, strings, pads), lead (synth lead, winds, voice),
   drums; parts with very few notes are dropped.
4. Notation: notation.quantize on the beat grid, strings and frets for guitar and bass,
   Guitar Pro 5 file (open it in alphaTab, Guitar Pro, TuxGuitar, MuseScore).

Usage: python transcribe_song.py <audio> <yourmt3 midi> <out.gp5>
"""

import json
import sys
from pathlib import Path

import numpy as np
import pretty_midi

import notation
from common import BEAT_THIS_CKPT, DEVICE
from test_multitrack import family

MIN_NOTES = 20
GM = {"guitar": 29, "bass": 33, "keys": 0, "lead": 81, "drums": 0}


def main() -> None:
    audio, midi, out = sys.argv[1], sys.argv[2], sys.argv[3]
    from beat_this.inference import File2Beats

    beats, downbeats = File2Beats(checkpoint_path=BEAT_THIS_CKPT, device=DEVICE, dbn=False)(audio)
    beats, downbeats = np.asarray(beats), np.asarray(downbeats)
    parts: dict[str, list] = {}
    for inst in pretty_midi.PrettyMIDI(midi).instruments:
        fam = family(inst.program, inst.is_drum)
        parts.setdefault(fam, []).extend((n.start, n.end, n.pitch) for n in inst.notes)
    tracks = []
    for fam in ("guitar", "bass", "keys", "lead", "drums"):
        notes = sorted(parts.get(fam, []))
        if len(notes) < MIN_NOTES:
            continue
        q = notation.quantize(notes, beats, monophonic=fam in ("bass", "lead"))
        tracks.append({"name": {"lead": "Lead / voice"}.get(fam, fam.capitalize()), "kind": "keys" if fam == "lead" else fam, "notes": q, "program": GM[fam]})
    notation.write_gp5(out, tracks, beats, downbeats, title=Path(audio).stem)
    summary = {t["name"]: len(t["notes"]) for t in tracks}
    print(json.dumps({"bpm": round(60 / float(np.median(np.diff(beats))), 1), "bars": len(downbeats), "notes": summary}))


if __name__ == "__main__":
    main()
