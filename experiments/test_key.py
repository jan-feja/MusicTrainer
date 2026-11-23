"""Key detection on real recordings of nine genres.

GTZAN (30 s excerpts) with the key annotations of Kraft, Lerch & Zölzer
(github.com/alexanderlerch/gtzan_key, put in MT_DATA/gtzan_key): one key per excerpt,
no classical (all marked unknown), excerpts marked "modulation / unknown" left out.

Methods:
  librosa_<profile>   CQT chroma (tuning-corrected) averaged over the excerpt, correlated with the
                      24 rotated key profiles; profiles: krumhansl, temperley, shaath (EDMKey),
                      bellman (Bellman-Budge)
  librosa_hpss_<p>    the same on the harmonic part only (librosa HPSS: drums mostly removed)
  madmom_cnn          madmom CNNKeyRecognitionProcessor (Korzeniowski & Widmer 2018, trained on
                      other datasets: GiantSteps-MTG, Billboard, ...)
Metrics (mir_eval.key, MIREX): accuracy (exact key) and weighted score (fifth 0.5, relative 0.3,
parallel 0.2). Also the share where the right key is one of the two best candidates (librosa),
for a "pick one of two" UI.
Estimates are cached in MT_DATA/key_estimates.json, song by song.

Usage: python test_key.py     (writes results/key.json)
"""

import json
from pathlib import Path

import librosa
import mir_eval
import numpy as np

from common import DATA, save_result

ROOT = Path(DATA, "gtzan_key", "dataset-gtzan-key-master", "gtzan_key", "genres")
AUDIO = Path(DATA, "gtzan", "genres")
NAMES = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]
PC = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

# major / minor profiles, index 0 = tonic
PROFILES = {
    "krumhansl": ([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
                  [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]),
    "temperley": ([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0],
                  [5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0]),
    "shaath": ([6.6, 2.0, 3.5, 2.3, 4.6, 4.0, 2.5, 5.2, 2.4, 3.7, 2.3, 3.4],
               [6.5, 2.7, 3.5, 5.4, 2.6, 3.5, 2.5, 5.2, 4.0, 2.7, 4.3, 3.2]),
    "bellman": ([16.80, 0.86, 12.95, 1.41, 13.49, 11.93, 1.25, 20.28, 1.80, 8.04, 0.62, 10.57],
                [18.16, 0.69, 12.99, 13.34, 1.07, 11.15, 1.38, 21.07, 7.49, 1.53, 0.92, 10.21]),
}


def label_to_key(label: int) -> str | None:
    if label < 0:
        return None
    return f"{NAMES[label % 12]} {'major' if label < 12 else 'minor'}"


def songs() -> list[tuple[Path, str]]:
    out = []
    for f in sorted(ROOT.glob("*/*.lerch.txt")):
        key = label_to_key(int(f.read_text().split()[0]))
        audio = AUDIO / f.parent.name / f.name.replace(".lerch.txt", ".wav")
        if key and audio.exists():
            out.append((audio, key))
    return out


def key_scores(chroma_mean: np.ndarray, profile: str) -> list[tuple[float, str]]:
    major, minor = (np.array(p) for p in PROFILES[profile])
    out = []
    for name, pc in PC.items():
        for prof, mode in ((major, "major"), (minor, "minor")):
            out.append((float(np.corrcoef(chroma_mean, np.roll(prof, pc))[0, 1]), f"{name} {mode}"))
    return sorted(out, reverse=True)


def same_key(a: str, b: str) -> bool:
    (ta, ma), (tb, mb) = a.split(), b.split()
    canon = lambda t: PC.get(t, PC.get({"Bb": "A#", "Eb": "D#", "Ab": "G#", "Db": "C#", "Gb": "F#"}.get(t, t), -1))  # noqa: E731
    return canon(ta) == canon(tb) and ma == mb


CACHE = Path(DATA, "key_estimates.json")
# mir_eval.key's weighted score identifies the kind of answer
KINDS = {1.0: "correct", 0.5: "fifth", 0.3: "relative", 0.2: "parallel", 0.0: "other"}


def estimate_all() -> dict:
    """{audio name: {"ref", method: [best key, second key]}}, cached song by song."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    madmom_key = None
    for audio, ref in songs():
        if audio.stem in cache:
            continue
        if madmom_key is None:
            from madmom.features.key import CNNKeyRecognitionProcessor

            madmom_key = CNNKeyRecognitionProcessor()
        from madmom.features.key import key_prediction_to_label

        y, sr = librosa.load(str(audio), sr=22050)
        tuning = librosa.estimate_tuning(y=y, sr=sr)
        row = {"ref": ref}
        for variant, signal in (("librosa", y), ("librosa_hpss", librosa.effects.harmonic(y))):
            chroma = librosa.feature.chroma_cqt(y=signal, sr=sr, tuning=tuning).mean(axis=1)
            for profile in PROFILES:
                row[f"{variant}_{profile}"] = [k for _, k in key_scores(chroma, profile)[:2]]
        prediction = madmom_key(str(audio))
        order = np.argsort(-prediction[0])
        row["madmom_cnn"] = [key_prediction_to_label(np.eye(24)[i][None]) for i in order[:2]]
        cache[audio.stem] = row
        CACHE.write_text(json.dumps(cache))
    return cache


def main() -> None:
    cache = estimate_all()
    refs = [row["ref"] for row in cache.values()]
    result = {"songs": len(refs)}
    for name in [k for k in next(iter(cache.values())) if k != "ref"]:
        weights = [mir_eval.key.evaluate(row["ref"], row[name][0])["Weighted Score"] for row in cache.values()]
        kinds = [KINDS[round(w, 1)] for w in weights]
        result[name] = {"accuracy": round(kinds.count("correct") / len(kinds), 3),
                        "weighted": round(float(np.mean(weights)), 3)}
        result[name] |= {k: round(kinds.count(k) / len(kinds), 3) for k in ("fifth", "relative", "parallel")}
        result[name]["right_in_top2"] = round(float(np.mean([any(same_key(k, row["ref"]) for k in row[name])
                                                             for row in cache.values()])), 3)
        print(name, result[name])
    save_result("key", result)


if __name__ == "__main__":
    main()
