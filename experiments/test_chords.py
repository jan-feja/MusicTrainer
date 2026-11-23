"""Chords on real recordings: the app's detector against the chords guitarists played.

GuitarSet comping excerpts (180: six guitarists, bossa nova, funk, jazz, rock, singer-songwriter;
microphone recordings). Each comes with its lead-sheet chords (e.g. Eb:maj7) and a beat grid.
The app's beats would come from Beat This!; here the annotated beats are used, so only the chord
recognition is measured.

Methods:
  app        backend music_trainer.services.chords.detect_chords (CQT chroma, triad templates,
             averaged per beat, Viterbi smoothing): the detector the app runs today
  app_bar    the same with one chord per bar at most (chords averaged over bars)
  madmom     madmom CNN chord features + CRF (major / minor), chords snapped to nothing
Metrics (mir_eval.chord, weighted by duration): majmin (root and major / minor right; sevenths
count as their triad), root; changes ratio = detected chord changes / true chord changes (> 1:
jumpier than the music).

Usage: python test_chords.py     (writes results/chords_real.json)
"""

import json
import sys
from pathlib import Path

import librosa
import mir_eval
import numpy as np

from common import DATA, save_result

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from music_trainer.services.chords import detect_chords  # noqa: E402

ROOT = Path(DATA, "guitarset")


def load(name: str) -> tuple[list, np.ndarray, np.ndarray]:
    data = json.loads((ROOT / "annotation" / f"{name}.jams").read_text())
    chords = next(a for a in data["annotations"] if a["namespace"] == "chord")  # the lead-sheet chords
    ref = [(c["time"], c["time"] + c["duration"], c["value"]) for c in chords["data"]]
    beats = next(a for a in data["annotations"] if a["namespace"] == "beat_position")["data"]
    times = np.array([b["time"] for b in beats])
    bars = np.array([b["time"] for b in beats if b["value"]["position"] == 1])
    return ref, times, bars


def scores(ref: list, est: list) -> dict:
    ri = np.array([[a, b] for a, b, _ in ref])
    rl = [l for _, _, l in ref]
    ei = np.array([[a, b] for a, b, _ in est])
    el = [l for _, _, l in est]
    ei, el = mir_eval.util.adjust_intervals(ei, el, ri.min(), ri.max(), mir_eval.chord.NO_CHORD, mir_eval.chord.NO_CHORD)
    intervals, r, e = mir_eval.util.merge_labeled_intervals(ri, rl, ei, el)
    durations = mir_eval.util.intervals_to_durations(intervals)
    out = {}
    for name, fn in (("majmin", mir_eval.chord.majmin), ("root", mir_eval.chord.root)):
        out[name] = float(mir_eval.chord.weighted_accuracy(fn(r, e), durations))
    changes = lambda labels: sum(a != b for a, b in zip(labels[:-1], labels[1:]))  # noqa: E731
    out["changes_ratio"] = (changes([l for _, _, l in est]) + 1) / (changes(rl) + 1)
    return out


def main() -> None:
    from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor

    feat, crf = CNNChordFeatureProcessor(), CRFChordRecognitionProcessor()
    rows: dict[str, list] = {}
    for jams in sorted((ROOT / "annotation").glob("*_comp.jams")):
        name = jams.stem
        ref, beats, bars = load(name)
        y, sr = librosa.load(str(ROOT / "audio_mono-mic" / f"{name}_mic.wav"), sr=22050)
        for method, grid in (("app", beats), ("app_bar", bars)):
            est = [(c.start, c.end, c.label) for c in detect_chords(y, sr, grid, separate_harmonics=False)]
            rows.setdefault(method, []).append(scores(ref, est))
        est = [(float(a), float(b), str(l)) for a, b, l in crf(feat(str(ROOT / "audio_mono-mic" / f"{name}_mic.wav")))]
        rows.setdefault("madmom", []).append(scores(ref, est))
    result = {m: {k: round(float(np.mean([r[k] for r in v])), 3) for k in v[0]} | {"excerpts": len(v)} for m, v in rows.items()}
    for m, r in result.items():
        print(m, r)
    save_result("chords_real", result)


if __name__ == "__main__":
    main()
