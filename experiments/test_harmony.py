"""Key, chord and tuning detection.

Key:    librosa chroma + Krumhansl profiles (simple baseline) vs madmom CNN
Chords: librosa chroma templates + Viterbi smoothing (baseline) vs madmom CNN+CRF
Tuning: librosa.estimate_tuning on detuned versions with known offsets
Ground truth: synthetic songs (exact). Real songs: methods compared with each other.
"""
import warnings

import librosa
import mir_eval
import numpy as np
import soundfile as sf

from common import harmonix_songs, load_gt, save_result, synth_dir

warnings.filterwarnings("ignore")
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ---------- key ----------
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def key_librosa(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    y = librosa.effects.harmonic(y)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(1)
    best = max(((np.corrcoef(chroma, np.roll(prof, k))[0, 1], f"{NOTES[k]} {mode}")
                for prof, mode in ((KS_MAJOR, "major"), (KS_MINOR, "minor")) for k in range(12)))
    return best[1]


def key_madmom(path):
    from madmom.features.key import CNNKeyRecognitionProcessor, key_prediction_to_label
    lab = key_prediction_to_label(CNNKeyRecognitionProcessor()(path))
    root, mode = lab.split()
    return f"{root} {mode}"


# ---------- chords ----------
def chord_templates():
    labels, T = [], []
    for k in range(12):
        for name, ivs in (("maj", (0, 4, 7)), ("min", (0, 3, 7))):
            t = np.zeros(12)
            t[[(k + i) % 12 for i in ivs]] = 1
            labels.append(f"{NOTES[k]}:{name}")
            T.append(t / np.linalg.norm(t))
    labels.append("N")
    T.append(np.ones(12) / np.sqrt(12) * 0.5)
    return labels, np.array(T)


def chords_librosa(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    hop = 2048
    chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=hop)
    chroma = librosa.util.normalize(chroma, norm=2, axis=0)
    labels, T = chord_templates()
    sim = T @ chroma  # (25, frames)
    prob = np.exp(sim * 8)
    prob /= prob.sum(0, keepdims=True)
    n = len(labels)
    trans = np.full((n, n), (1 - 0.95) / (n - 1))
    np.fill_diagonal(trans, 0.95)
    path_ = librosa.sequence.viterbi(prob, trans)
    times = librosa.frames_to_time(np.arange(len(path_) + 1), sr=sr, hop_length=hop)
    ints, labs = [], []
    for i, p in enumerate(path_):
        if labs and labs[-1] == labels[p]:
            ints[-1][1] = times[i + 1]
        else:
            ints.append([times[i], times[i + 1]])
            labs.append(labels[p])
    return np.array(ints), labs


def chords_madmom(path):
    from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor
    feats = CNNChordFeatureProcessor()(path)
    res = CRFChordRecognitionProcessor()(feats)
    return np.array([[r[0], r[1]] for r in res]), [r[2] for r in res]


def gt_chords(gt):
    ints = np.array([[a, b] for a, b, _ in gt["chords"]])
    labs = [c[:-1] + ":min" if c.endswith("m") else c + ":maj" for _, _, c in gt["chords"]]
    return ints, labs


def chord_score(ref, est):
    ri, rl = ref
    ei, el = est
    ei, el = mir_eval.util.adjust_intervals(ei, el, ri.min(), ri.max(), mir_eval.chord.NO_CHORD, mir_eval.chord.NO_CHORD)
    ints, r, e = mir_eval.util.merge_labeled_intervals(ri, rl, ei, el)
    dur = mir_eval.util.intervals_to_durations(ints)
    return float(mir_eval.chord.weighted_accuracy(mir_eval.chord.majmin(r, e), dur))


def main(parts):
    import json, os
    from common import RESULTS
    path = os.path.join(RESULTS, "harmony.json")
    res = json.load(open(path)) if os.path.exists(path) else {"key": {}, "chords": {}, "tuning": {}}
    variants = ("steady", "live", "detune", "eb")
    if "key" in parts:
        run_key(res, variants)
    if "chords" in parts:
        run_chords(res, variants)
    if "tuning" in parts:
        res["tuning"] = {}
        run_tuning(res)
    save_result("harmony", res)


def run_key(res, variants):
    print("== Key (synthetic, exact truth) ==")
    for v in variants:
        gt = load_gt(v)
        p = f"{synth_dir(v)}/mix.wav"
        row = {"truth": gt["key"]}
        for name, fn in (("librosa", key_librosa), ("madmom", key_madmom)):
            try:
                row[name] = fn(p)
                row[name + "_score"] = mir_eval.key.weighted_score(gt["key"], row[name])
            except Exception as e:
                row[name] = f"n/a ({type(e).__name__})"
        res["key"][v] = row
        print(v, row)
    print("== Key (real songs, no truth: do the methods agree?) ==")
    for sid, wav, _ in harmonix_songs():
        row = {}
        for name, fn in (("librosa", key_librosa), ("madmom", key_madmom)):
            try:
                row[name] = fn(wav)
            except Exception as e:
                row[name] = f"n/a ({type(e).__name__})"
        res["key"][sid] = row
        print(f"{sid:28s} {row}")



def run_chords(res, variants):
    print("== Chords (synthetic, majmin weighted accuracy) ==")
    for v in variants:
        gt = load_gt(v)
        p = f"{synth_dir(v)}/mix.wav"
        row = {}
        for name, fn in (("librosa", chords_librosa), ("madmom", chords_madmom)):
            try:
                row[name] = chord_score(gt_chords(gt), fn(p))
            except Exception as e:
                row[name] = f"n/a ({type(e).__name__}: {e})"
        res["chords"][v] = row
        print(v, row)
    # chords on a real song, first 40 s, to eyeball
    sid, wav, _ = harmonix_songs()[0]
    for name, fn in (("librosa", chords_librosa), ("madmom", chords_madmom)):
        try:
            ints, labs = fn(wav)
            seq = [f"{a:.1f}:{l}" for (a, b), l in zip(ints, labs) if a < 40 and b - a > 0.4]
            print(f"{sid} {name}: {' '.join(seq)}")
            res["chords"][f"{sid}_{name}_first40s"] = seq
        except Exception as e:
            print(name, "n/a", e)



def run_tuning(res):
    print("== Tuning (cents; librosa.estimate_tuning) ==")
    for v in ("steady", "detune", "eb"):
        y, sr = librosa.load(f"{synth_dir(v)}/mix.wav", sr=22050)
        est = 100 * librosa.estimate_tuning(y=y, sr=sr)
        truth = load_gt(v)["tuning_cents"]
        res["tuning"][f"synth_{v}"] = {"truth": truth, "estimate": est}
        print(f"synth_{v:8s} truth {truth:+4d} (eb = whole semitone)  estimate {est:+6.1f}")
    from pedalboard import time_stretch
    for sid, wav, _ in harmonix_songs()[:4]:
        y, sr = librosa.load(wav, sr=22050, duration=60)
        base = 100 * librosa.estimate_tuning(y=y, sr=sr)
        for shift in (-30, 20):
            ys = time_stretch(y[None].astype(np.float32), sr, 1.0, pitch_shift_in_semitones=shift / 100)[0]
            est = 100 * librosa.estimate_tuning(y=ys, sr=sr)
            res["tuning"][f"{sid}_{shift:+d}"] = {"base": base, "shift": shift, "estimate": est, "measured_shift": est - base}
            print(f"{sid:28s} original {base:+5.1f}  shifted {shift:+d} -> measured {est - base:+5.1f}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or ["key", "chords", "tuning"])
