"""Transcription of real recordings, against aligned fan-made MIDI files (a rough answer key).

The synthetic score songs give exact answers but synthetic sound. Here: the real songs whose Lakh
MIDI file aligned well to the YouTube recording (test_import_alignment.py, synctoolbox + snapping
to beats, >= 70 % of annotated beats within 100 ms); the best-aligned MIDI file per song. Its
notes, moved into the recording's time, are the reference per instrument family.

The reference is rough: fan arrangements leave parts out or simplify them, octaves can differ
(bass written an octave up), and the alignment is off by ~45 ms typically. So: onset tolerance
100 ms, and two pitch rules: exact pitch, and pitch class (octave errors forgiven). Numbers are
for comparing methods with each other, not absolute quality.

Methods: YourMT3+ on the mix (transcription/real_ymt3), htdemucs_6s + Basic Pitch + ADTOF
(computed here: python test_real_transcription.py pipeline).

Usage: python test_real_transcription.py separate      (Demucs; separate process from the next step)
       python test_real_transcription.py transcribe    (Basic Pitch, ADTOF)
       python test_real_transcription.py               (writes results/real_transcription.json)
"""

import json
import sys
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

from common import DATA, DEVICE, save_result
from test_multitrack import FAMILIES, RANGES, STEM_FAMILY, _write_midi, drum_f, family

RESULTS = Path(__file__).with_name("results") / "import_alignment.json"
WORK = Path(DATA, "transcription")


def selected() -> list[tuple[str, str]]:
    """(song, midi file name) of the best-aligned file per song, if good enough."""
    rows = json.loads(RESULTS.read_text())["per_file"]
    best: dict[str, tuple[float, str]] = {}
    for key, row in rows.items():
        song, midi = key.split("/", 1)
        r = row.get("synctoolbox+beats", {})
        if "within_100ms" in r and r["within_100ms"] >= 0.7 and r["within_100ms"] > best.get(song, (0, ""))[0]:
            best[song] = (r["within_100ms"], midi)
    return [(song, midi) for song, (_, midi) in sorted(best.items())]


def lakh_path(song: str, midi_name: str) -> Path:
    from test_import_alignment import matches

    return next(f for s, files in matches() if s == song for f in files if f.name == midi_name)


def reference(song: str, midi_name: str) -> dict[str, np.ndarray]:
    from test_import_alignment import CACHE, norm  # pandas / synctoolbox: kept out of the TensorFlow stage

    path = np.load(CACHE / f"synctoolbox__{song}__{norm(Path(midi_name).stem)}.npz")
    audio_t, score_t = path["audio_t"], path["score_t"]
    order = np.argsort(score_t)
    warp = lambda t: np.interp(t, score_t[order], audio_t[order])  # noqa: E731
    out: dict[str, list] = {}
    for inst in pretty_midi.PrettyMIDI(str(lakh_path(song, midi_name))).instruments:
        fam = family(inst.program, inst.is_drum)
        out.setdefault(fam, []).extend((warp(n.start), warp(n.end), n.pitch) for n in inst.notes
                                       if score_t.min() <= n.start <= score_t.max())
    return {k: np.array(v, dtype=float) for k, v in out.items()}


def estimate(path: Path) -> dict[str, np.ndarray]:
    out: dict[str, list] = {}
    for inst in pretty_midi.PrettyMIDI(str(path)).instruments:
        out.setdefault(family(inst.program, inst.is_drum), []).extend((n.start, n.end, n.pitch) for n in inst.notes)
    return {k: np.array(v, dtype=float).reshape(-1, 3) for k, v in out.items()}


def note_f(ref: np.ndarray, est: np.ndarray, pitch_class: bool) -> float:
    if len(ref) == 0 or len(est) == 0:
        return 0.0
    r, e = ref.copy(), est.copy()
    if pitch_class:
        r[:, 2], e[:, 2] = 60 + r[:, 2] % 12, 60 + e[:, 2] % 12
    hz = mir_eval.util.midi_to_hz
    return float(mir_eval.transcription.precision_recall_f1_overlap(
        r[:, :2], hz(r[:, 2]), e[:, :2], hz(e[:, 2]), onset_tolerance=0.1, offset_ratio=None)[2])


def separate() -> None:
    """Stage 1 (PyTorch only: Demucs and TensorFlow in one process crash)."""
    import soundfile as sf

    from test_separation import demucs_separate

    for song, _ in selected():
        stem_dir = WORK / "stems" / "real_htdemucs_6s" / song
        if (stem_dir / "drums.wav").exists():
            continue
        mix, sr = sf.read(Path(DATA, "songs", f"{song}.wav"), always_2d=True)
        stem_dir.mkdir(parents=True, exist_ok=True)
        for stem, audio in demucs_separate("htdemucs_6s", mix, sr, DEVICE).items():
            sf.write(stem_dir / f"{stem}.wav", audio, sr, subtype="FLOAT")
        print("separated", song, flush=True)


def transcribe() -> None:
    """Stage 2: Basic Pitch per stem, ADTOF on the drum stem."""
    from adtof_pytorch import transcribe_to_midi
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import Model, predict

    model = Model(ICASSP_2022_MODEL_PATH)
    for song, _ in selected():
        out = WORK / "real_bp_demucs" / f"{song}.mid"
        stem_dir = WORK / "stems" / "real_htdemucs_6s" / song
        if out.exists() or not (stem_dir / "drums.wav").exists():
            continue
        notes: dict[str, list] = {}
        for wav in sorted(stem_dir.glob("*.wav")):
            fam = STEM_FAMILY[wav.stem]
            if fam == "drums":
                tmp = WORK / "adtof_tmp.mid"
                transcribe_to_midi(str(wav), str(tmp), device=DEVICE)
                notes["drums"] = [(n.start, n.end, n.pitch) for i in pretty_midi.PrettyMIDI(str(tmp)).instruments for n in i.notes]
            else:
                lo, hi = RANGES[fam]
                _, _, events = predict(str(wav), model, minimum_frequency=lo, maximum_frequency=hi, melodia_trick=fam in ("bass", "lead"))
                notes.setdefault(fam, []).extend((e[0], e[1], e[2]) for e in events)
        _write_midi(out, notes)
        print("transcribed", song, flush=True)


def main() -> None:
    rows = {}
    for song, midi in selected():
        ref = reference(song, midi)
        for method, folder in (("ymt3_mix", "real_ymt3"), ("bp_demucs", "real_bp_demucs")):
            path = WORK / folder / f"{song}.mid"
            if not path.exists():
                continue
            est = estimate(path)
            row = {}
            for fam in FAMILIES:
                if fam in ref and len(ref[fam]) >= 20:
                    row[fam] = round(note_f(ref[fam], est.get(fam, np.zeros((0, 3))), False), 3)
                    row[fam + "/pitch_class"] = round(note_f(ref[fam], est.get(fam, np.zeros((0, 3))), True), 3)
            if "drums" in ref:
                classes = drum_f(ref["drums"], est.get("drums", np.zeros((0, 3))))
                row["drums"] = round(float(np.mean(list(classes.values()))), 3) if classes else 0.0
            rows.setdefault(method, {})[f"{song} ({midi})"] = row
    summary = {}
    for method, songs in rows.items():
        keys = sorted({k for r in songs.values() for k in r})
        summary[method] = {k: round(float(np.mean([r[k] for r in songs.values() if k in r])), 3) for k in keys} | {"songs": len(songs)}
    print(json.dumps(summary, indent=1))
    save_result("real_transcription", {"summary": summary, "per_song": rows, "reference_files": selected()})


if __name__ == "__main__":
    {"separate": separate, "transcribe": transcribe, "evaluate": main}[sys.argv[1] if len(sys.argv) > 1 else "evaluate"]()
