"""Render the score songs again, keeping every instrument's stem and its exact notes.

score_to_audio.py writes only the mix. Transcription per instrument needs more: the notes
each part really played (after the timing jitter) and the clean stem, to tell transcription
errors from separation errors. Rendering is the same (FluidSynth, jitter, effects, levels,
compressed mix), so the songs sound like the ones the beat experiments use.

For the first variant of every score song, MT_DATA/score_stems/<name>/ gets:
  mix.wav               44.1 kHz stereo, 1 s lead-in
  stems/<family>.wav    drums, bass, guitar, keys, lead (each scaled as in the mix)
  notes.json            {family: [[onset, offset, pitch, program], ...]} in mix time

Usage: python render_score_stems.py      (needs FLUIDSYNTH and SOUNDFONT, like score_to_audio.py)
"""

import json
import os
import random
import re
import subprocess
import tempfile
import zlib
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

from common import DATA
from score_to_audio import JITTER, LEAD_IN, LOUDNESS_DB, SR, TAIL, effects, family

OUT = Path(DATA, "score_stems")


def render_with_stems(midi_path: Path, out_dir: Path, meta: dict, seed: int) -> None:
    from pedalboard import Compressor, Limiter, Pedalboard

    fluidsynth, soundfont = os.environ["FLUIDSYNTH"], os.environ["SOUNDFONT"]
    rnd = random.Random(seed)
    np_rnd = np.random.default_rng(seed)
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    humanize = float(meta.get("humanize", 1.0))
    preset = meta.get("effects", "band")
    stems: dict[str, np.ndarray] = {}
    notes: dict[str, list] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for k, inst in enumerate(pm.instruments):
            if not inst.notes:
                continue
            fam = family(inst)
            part = pretty_midi.PrettyMIDI(resolution=pm.resolution, initial_tempo=120)
            copy = pretty_midi.Instrument(inst.program, is_drum=inst.is_drum, name=inst.name)
            lag = 0.0 if fam == "drums" else rnd.uniform(-0.004, 0.010) * humanize
            for n in inst.notes:
                jitter = float(np_rnd.normal(0, JITTER[fam] * humanize)) + lag
                start = max(0.0, n.start + jitter)
                copy.notes.append(pretty_midi.Note(n.velocity, n.pitch, start, max(start + 0.03, n.end + jitter)))
            part.instruments.append(copy)
            mid, wav = Path(tmp) / f"{k}.mid", Path(tmp) / f"{k}.wav"
            part.write(str(mid))
            subprocess.run([fluidsynth, "-ni", "-q", "-g", "0.5", "-r", str(SR), "-F", str(wav), soundfont, str(mid)],
                           check=True, capture_output=True)
            audio, _ = sf.read(wav, dtype="float32", always_2d=True)
            audio = effects(fam, inst.program, preset, rnd)(audio.T.copy(), SR).T
            rms = np.sqrt(np.mean(audio**2)) + 1e-9
            target = 10 ** ((LOUDNESS_DB[fam] + rnd.uniform(-2, 2)) / 20)
            audio = audio * target / rms
            if fam in stems:
                n = max(len(stems[fam]), len(audio))
                stems[fam] = np.pad(stems[fam], ((0, n - len(stems[fam])), (0, 0))) + np.pad(audio, ((0, n - len(audio)), (0, 0)))
            else:
                stems[fam] = audio
            notes.setdefault(fam, []).extend(
                [round(float(n.start) + LEAD_IN, 5), round(float(n.end) + LEAD_IN, 5), int(n.pitch), int(inst.program)]
                for n in copy.notes)
    n = max(len(s) for s in stems.values())
    music_end = max(note.end for inst in pm.instruments for note in inst.notes)
    length = int((music_end + TAIL) * SR)
    lead = np.zeros((int(LEAD_IN * SR), 2), dtype=np.float32)
    padded = {f: np.concatenate([lead, np.pad(s, ((0, n - len(s)), (0, 0)))[:length]]) for f, s in stems.items()}
    mix = sum(padded.values())
    mix = Pedalboard([Compressor(threshold_db=-14, ratio=2.5), Limiter(threshold_db=-1.0)])(mix.T.copy(), SR).T
    scale = 0.89 / (np.abs(mix).max() + 1e-9)
    (out_dir / "stems").mkdir(parents=True, exist_ok=True)
    sf.write(out_dir / "mix.wav", mix * scale, SR, subtype="PCM_16")
    for fam, audio in padded.items():  # stems at mix level (before the bus compressor)
        sf.write(out_dir / "stems" / f"{fam}.wav", audio * scale, SR, subtype="FLOAT")
    (out_dir / "notes.json").write_text(json.dumps({f: sorted(v) for f, v in notes.items()}))


def main() -> None:
    for folder in ("score_songs", "score_songs_changes"):
        for song_dir in sorted(Path(DATA, folder).iterdir()):
            if not (song_dir / "song.mid").exists() or re.search(r"_v\d$", song_dir.name) or song_dir.name == "bass":
                continue
            out = OUT / song_dir.name
            if (out / "notes.json").exists():
                continue
            sidecar = Path(DATA, "score_midi" if folder == "score_songs" else "score_midi_changes", f"{song_dir.name}.json")
            meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
            render_with_stems(song_dir / "song.mid", out, meta, seed=zlib.crc32(song_dir.name.encode()) % 10_000)
            print(song_dir.name, flush=True)


if __name__ == "__main__":
    main()
