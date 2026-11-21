"""Audio -> notes (the basis for showing notes / tabs and for scoring a take).

Pitched instruments: Spotify Basic Pitch.  Drums: ADTOF (PyTorch port).
Each runs twice on the synthetic song:
  clean      on the true instrument stem (best case)
  separated  on the stem Demucs (htdemucs_6s) pulls out of the full mix (what the app will have)
Metric: note F-measure (onset within 50 ms and correct pitch; mir_eval).
"""
import os
import warnings

import mir_eval
import numpy as np
import pretty_midi
import soundfile as sf

from common import DATA, DEVICE, save_result, synth_dir

warnings.filterwarnings("ignore")
RANGES = {"bass": (30, 400), "guitar": (70, 1400), "piano": (60, 2000), "vocals": (150, 1200)}
DRUM_CLASSES = {"kick": [35, 36], "snare": [38, 40], "toms": [45, 47, 48, 50], "hihat": [42, 44, 46], "cymbals": [49, 51, 57]}
_model = None


def basic_pitch_notes(path, stem):
    global _model
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import Model, predict
    if _model is None:
        _model = Model(ICASSP_2022_MODEL_PATH)
    lo, hi = RANGES[stem]
    _, _, events = predict(path, _model, minimum_frequency=lo, maximum_frequency=hi,
                           melodia_trick=stem in ("bass", "vocals"))
    return np.array([[e[0], e[1]] for e in events]), np.array([e[2] for e in events])


def adtof_notes(path):
    from adtof_pytorch import transcribe_to_midi
    out = path.replace(".wav", "_adtof.mid")
    transcribe_to_midi(path, out, device=DEVICE)
    pm = pretty_midi.PrettyMIDI(out)
    return [(n.start, n.pitch) for inst in pm.instruments for n in inst.notes]


def ref_notes(stem):
    pm = pretty_midi.PrettyMIDI(os.path.join(synth_dir("steady"), f"{stem}.mid"))
    notes = pm.instruments[0].notes
    return np.array([[n.start, n.end] for n in notes]), np.array([n.pitch for n in notes])


def note_f(ref, est):
    (ri, rp), (ei, ep) = ref, est
    if len(ei) == 0:
        return 0.0, 0.0, 0.0
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ri, mir_eval.util.midi_to_hz(rp), ei, mir_eval.util.midi_to_hz(ep), onset_tolerance=0.05, offset_ratio=None)
    return p, r, f


def drum_scores(est_notes):
    pm = pretty_midi.PrettyMIDI(os.path.join(synth_dir("steady"), "drums.mid"))
    ref = [(n.start, n.pitch) for n in pm.instruments[0].notes]
    out = {}
    for cls, pitches in DRUM_CLASSES.items():
        r = np.array(sorted(t for t, p in ref if p in pitches))
        e = np.array(sorted(t for t, p in est_notes if p in pitches))
        if len(r) == 0:
            continue
        out[cls] = float(mir_eval.onset.f_measure(r, e, window=0.05)[0]) if len(e) else 0.0
    return out


def separated_stems():
    """Run htdemucs_6s once on the synthetic mix and cache the stems."""
    out_dir = os.path.join(DATA, "synth_steady_separated")
    if not os.path.exists(os.path.join(out_dir, "bass.wav")):
        from test_separation import demucs_separate
        os.makedirs(out_dir, exist_ok=True)
        mix, sr = sf.read(os.path.join(synth_dir("steady"), "mix.wav"), always_2d=True)
        for s, y in demucs_separate("htdemucs_6s", mix, sr, DEVICE).items():
            sf.write(os.path.join(out_dir, f"{s}.wav"), y, sr)
    return out_dir


def main():
    sep_dir = separated_stems()
    res = {}
    for stem in ("bass", "guitar", "piano", "vocals"):
        ref = ref_notes(stem)
        for cond, path in (("clean", os.path.join(synth_dir("steady"), "stems", f"{stem}.wav")),
                           ("separated", os.path.join(sep_dir, f"{stem}.wav"))):
            p, r, f = note_f(ref, basic_pitch_notes(path, stem))
            res[f"{stem}/{cond}"] = dict(precision=p, recall=r, f=f)
            print(f"basic-pitch {stem:7s} {cond:9s} P={p:.2f} R={r:.2f} F={f:.2f}  ({len(ref[0])} true notes)")
    for cond, path in (("clean", os.path.join(synth_dir("steady"), "stems", "drums.wav")),
                       ("separated", os.path.join(sep_dir, "drums.wav"))):
        try:
            sc = drum_scores(adtof_notes(path))
            res[f"drums/{cond}"] = sc
            print(f"ADTOF drums {cond:9s} " + " ".join(f"{k}={v:.2f}" for k, v in sc.items()))
        except Exception as e:
            res[f"drums/{cond}"] = {"error": f"{type(e).__name__}: {e}"}
            print("ADTOF unavailable:", e)
    save_result("transcription", res)


if __name__ == "__main__":
    main()
