"""Notes for every instrument of a full song: which pipeline gets them?

Test songs: the score songs rendered with stems (render_score_stems.py): 28 songs, 41 minutes,
drums, bass, guitar (clean and distorted), keys (piano, organ, strings, pads, accordion) and
a few leads (flute, saxophone, synth), each note known exactly.

Pipelines:
  bp_clean        Basic Pitch on the true stem of each instrument (no separation: best case)
  bp_demucs       htdemucs_6s (the app's separator) -> Basic Pitch per stem, ADTOF on drums
  bp_roformer     BS-RoFormer-SW (6 stems) -> Basic Pitch per stem, ADTOF on drums
  ymt3_mix        YourMT3+ on the mix: one model names the instrument of every note
  ymt3_demucs     YourMT3+ on each htdemucs_6s stem, keeping the notes of that stem's family
  ymt3_clean      YourMT3+ on each true stem (best case for YourMT3+)
Stems map to families: bass, drums, guitar, piano -> keys, other + vocals -> lead.

Metrics (mir_eval, onset within 50 ms, offsets ignored):
  pitched families  note F-measure (right pitch; for ymt3_mix also the right family)
  drums             onset F-measure per class (kick, snare, hi-hat, toms, cymbals), averaged
  all pitched       note F-measure over every pitched note, whatever the instrument

Stages (each caches under MT_DATA/transcription/; run in this order):
  python test_multitrack.py separate      htdemucs_6s stems           (venv with demucs)
  python test_multitrack.py roformer      BS-RoFormer-SW stems        (venv with bs_roformer)
  python test_multitrack.py basic-pitch   Basic Pitch and ADTOF       (venv with basic_pitch, adtof)
  python test_multitrack.py yourmt3       YourMT3+ (runs yourmt3_runner.py; venv of YourMT3+)
  python test_multitrack.py evaluate      results/multitrack.json
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from common import DATA, DEVICE, save_result

SONGS = Path(DATA, "score_stems")
WORK = Path(DATA, "transcription")
FAMILIES = ("bass", "guitar", "keys", "lead")
STEM_FAMILY = {"bass": "bass", "guitar": "guitar", "piano": "keys", "other": "lead", "vocals": "lead", "drums": "drums"}
# Basic Pitch frequency limits per family (Hz)
RANGES = {"bass": (30, 400), "guitar": (70, 1400), "keys": (27, 4200), "lead": (100, 2500)}
DRUM_CLASSES = {"kick": {35, 36}, "snare": {37, 38, 39, 40}, "toms": {41, 43, 45, 47, 48, 50},
                "hihat": {42, 44, 46}, "cymbals": {49, 51, 52, 53, 55, 57, 59}}


def songs() -> list[str]:
    return sorted(p.parent.name for p in SONGS.glob("*/notes.json"))


def family(program: int, is_drum: bool) -> str:
    """Same families as score_to_audio.family."""
    if is_drum:
        return "drums"
    if 32 <= program <= 39:
        return "bass"
    if 24 <= program <= 31:
        return "guitar"
    if program in range(40, 56) or program in range(88, 104) or program < 24:
        return "keys"
    return "lead"


# --- stages ----------------------------------------------------------------------------------


def separate_demucs() -> None:
    import soundfile as sf

    from test_separation import demucs_separate

    for song in songs():
        out = WORK / "stems" / "htdemucs_6s" / song
        if (out / "drums.wav").exists():
            continue
        mix, sr = sf.read(SONGS / song / "mix.wav", always_2d=True)
        out.mkdir(parents=True, exist_ok=True)
        for stem, audio in demucs_separate("htdemucs_6s", mix, sr, DEVICE).items():
            sf.write(out / f"{stem}.wav", audio, sr, subtype="FLOAT")
        print("demucs", song, flush=True)


def separate_roformer() -> None:
    import shutil
    import tempfile

    from bs_roformer import BSRoformerSession

    todo = [s for s in songs() if not (WORK / "stems" / "roformer_sw" / s / "drums.wav").exists()]
    if not todo:
        return
    with tempfile.TemporaryDirectory() as tmp, BSRoformerSession(device=DEVICE) as session:
        for song in todo:
            src = Path(tmp, "in", f"{song}.wav")
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SONGS / song / "mix.wav", src)
            session.infer(str(src.parent), store_dir=str(Path(tmp, "out")))
            out = WORK / "stems" / "roformer_sw" / song
            out.mkdir(parents=True, exist_ok=True)
            for f in Path(tmp, "out").rglob("*.wav"):
                stem = next((s for s in STEM_FAMILY if s in f.stem.lower()), None)
                if stem:
                    shutil.move(str(f), out / f"{stem}.wav")
            shutil.rmtree(Path(tmp, "out"), ignore_errors=True)
            src.unlink()
            print("roformer", song, sorted(p.stem for p in out.glob("*.wav")), flush=True)


def _write_midi(path: Path, notes_by_family: dict[str, list]) -> None:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI()
    programs = {"bass": 33, "guitar": 25, "keys": 0, "lead": 81}
    for fam, notes in notes_by_family.items():
        inst = pretty_midi.Instrument(0 if fam == "drums" else programs[fam], is_drum=fam == "drums", name=fam)
        for onset, offset, pitch in notes:
            inst.notes.append(pretty_midi.Note(80, int(pitch), float(onset), float(max(offset, onset + 0.02))))
        pm.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


def basic_pitch_and_adtof() -> None:
    import pretty_midi
    from adtof_pytorch import transcribe_to_midi
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import Model, predict

    model = Model(ICASSP_2022_MODEL_PATH)

    def bp(path: Path, fam: str) -> list:
        lo, hi = RANGES[fam]
        _, _, events = predict(str(path), model, minimum_frequency=lo, maximum_frequency=hi,
                               melodia_trick=fam in ("bass", "lead"))
        return [(e[0], e[1], e[2]) for e in events]

    def drums(path: Path) -> list:
        tmp = WORK / "adtof_tmp.mid"
        transcribe_to_midi(str(path), str(tmp), device=DEVICE)
        pm = pretty_midi.PrettyMIDI(str(tmp))
        return [(n.start, n.end, n.pitch) for inst in pm.instruments for n in inst.notes]

    for song in songs():
        conditions = {"bp_clean": SONGS / song / "stems",
                      "bp_demucs": WORK / "stems" / "htdemucs_6s" / song,
                      "bp_roformer": WORK / "stems" / "roformer_sw" / song}
        for method, stem_dir in conditions.items():
            out = WORK / method / f"{song}.mid"
            if out.exists() or not stem_dir.exists():
                continue
            notes: dict[str, list] = {}
            for wav in sorted(stem_dir.glob("*.wav")):
                fam = wav.stem if method == "bp_clean" else STEM_FAMILY.get(wav.stem)
                if fam is None:
                    continue
                notes.setdefault(fam, []).extend(drums(wav) if fam == "drums" else bp(wav, fam))
            _write_midi(out, notes)
            print(method, song, flush=True)


def yourmt3() -> None:
    py = os.environ.get("YOURMT3_PYTHON", sys.executable)
    runner = str(Path(__file__).with_name("yourmt3_runner.py"))
    jobs = {"ymt3_mix": [f"{s}::{SONGS / s / 'mix.wav'}" for s in songs()]}
    for method, root in (("ymt3_clean", None), ("ymt3_demucs", WORK / "stems" / "htdemucs_6s")):
        jobs[f"{method}_raw"] = [f"{s}__{w.stem}::{w}" for s in songs()
                                 for w in sorted((SONGS / s / "stems" if root is None else root / s).glob("*.wav"))]
    for method, args in jobs.items():
        subprocess.run([py, runner, str(WORK / method)] + args, check=True)


# --- evaluation ------------------------------------------------------------------------------


def reference(song: str) -> dict[str, np.ndarray]:
    data = json.loads((SONGS / song / "notes.json").read_text())
    return {fam: np.array([n[:3] for n in notes], dtype=float) for fam, notes in data.items()}


def midi_notes(path: Path, keep_family: str | None = None) -> dict[str, list]:
    """{family: [(onset, offset, pitch)]}; with keep_family, every note of that family only."""
    import pretty_midi

    out: dict[str, list] = {}
    for inst in pretty_midi.PrettyMIDI(str(path)).instruments:
        fam = family(inst.program, inst.is_drum)
        if keep_family and fam != keep_family:
            continue
        out.setdefault(fam, []).extend((n.start, n.end, n.pitch) for n in inst.notes)
    return out


def estimate(method: str, song: str) -> dict[str, np.ndarray] | None:
    if method in ("ymt3_clean", "ymt3_demucs"):
        raw = WORK / f"{method}_raw"
        files = sorted(raw.glob(f"{song}__*.mid"))
        if not files:
            return None
        out: dict[str, list] = {}
        for f in files:
            stem = f.stem.split("__", 1)[1]
            fam = stem if method == "ymt3_clean" else STEM_FAMILY[stem]
            for k, v in midi_notes(f, keep_family=fam).items():
                out.setdefault(k, []).extend(v)
    else:
        path = WORK / method / f"{song}.mid"
        if not path.exists():
            return None
        out = midi_notes(path)
    return {k: np.array(v, dtype=float).reshape(-1, 3) for k, v in out.items()}


def note_prf(ref: np.ndarray, est: np.ndarray) -> tuple[float, float, float]:
    import mir_eval

    if len(ref) == 0 and len(est) == 0:
        return 1.0, 1.0, 1.0
    if len(ref) == 0 or len(est) == 0:
        return 0.0, 0.0, 0.0
    hz = mir_eval.util.midi_to_hz
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref[:, :2], hz(ref[:, 2]), est[:, :2], hz(est[:, 2]), onset_tolerance=0.05, offset_ratio=None)
    return p, r, f


def drum_f(ref: np.ndarray, est: np.ndarray) -> dict[str, float]:
    import mir_eval

    out = {}
    for cls, pitches in DRUM_CLASSES.items():
        r = np.sort(ref[np.isin(ref[:, 2], list(pitches)), 0]) if len(ref) else np.array([])
        if len(r) == 0:
            continue
        e = np.sort(est[np.isin(est[:, 2], list(pitches)), 0]) if len(est) else np.array([])
        out[cls] = float(mir_eval.onset.f_measure(r, e, window=0.05)[0]) if len(e) else 0.0
    return out


def evaluate() -> None:
    methods = ("bp_clean", "bp_demucs", "bp_roformer", "ymt3_mix", "ymt3_demucs", "ymt3_clean")
    per_song: dict[str, dict] = {}
    totals: dict[str, dict] = {}
    for method in methods:
        rows = {}
        for song in songs():
            est = estimate(method, song)
            if est is None:
                continue
            ref = reference(song)
            row = {}
            for fam in FAMILIES:
                if fam in ref:
                    row[fam] = note_prf(ref[fam], est.get(fam, np.zeros((0, 3))))[2]
            if "drums" in ref:
                classes = drum_f(ref["drums"], est.get("drums", np.zeros((0, 3))))
                row["drums"] = float(np.mean(list(classes.values())))
                row.update({f"drums/{k}": v for k, v in classes.items()})
            pitched_ref = np.concatenate([ref[f] for f in FAMILIES if f in ref])
            pitched_est = [est[f] for f in FAMILIES if f in est]
            row["all_pitched"] = note_prf(pitched_ref, np.concatenate(pitched_est) if pitched_est else np.zeros((0, 3)))[2]
            rows[song] = {k: round(v, 3) for k, v in row.items()}
        if not rows:
            continue
        per_song[method] = rows
        keys = sorted({k for r in rows.values() for k in r})
        totals[method] = {k: round(float(np.mean([r[k] for r in rows.values() if k in r])), 3) for k in keys}
        totals[method]["songs"] = len(rows)
        print(method, json.dumps(totals[method]))
    save_result("multitrack", {"mean_f": totals, "per_song": per_song})


if __name__ == "__main__":
    stage = sys.argv[1]
    {"separate": separate_demucs, "roformer": separate_roformer, "basic-pitch": basic_pitch_and_adtof,
     "yourmt3": yourmt3, "evaluate": evaluate}[stage]()
