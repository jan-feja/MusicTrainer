"""Tuning: how far from A440 are real recordings, and does it matter for transcription?

1. Real recordings: librosa.estimate_tuning on the Harmonix and SALAMI songs of the structure
   manifest (decades of studio and live recordings): the share more than 15 / 25 cents off.
2. Transcription of detuned audio: score songs played back faster or slower (resampling: pitch
   and tempo move together) by -45, -25, +25 and +45 cents; transcribed as they are, and after
   detecting the tuning and resampling back to A440. Metric: note F over all pitched notes
   (right pitch, onset within 50 ms; reference times scaled with the playback rate).

Usage:
  python test_tuning.py survey                 (librosa venv)
  python test_tuning.py render                 writes the detuned and corrected mixes
  python yourmt3_runner.py ...                 (printed by: python test_tuning.py jobs)
  python test_tuning.py evaluate               writes results/tuning.json
"""

import json
import sys
from pathlib import Path

import numpy as np

from common import DATA, save_result

WORK = Path(DATA, "tuning")
SONGS = ["rock_120", "funk_100", "ballad_75_feels", "acoustic_nodrums_85", "metal_180", "swing_160", "waltz_3-4_150", "reggae_onedrop_75"]
CENTS = (-45, -25, 25, 45)


def survey() -> None:
    import librosa

    import structure_common as sc

    rows = {}
    for song in sc.load_manifest():
        if song.set not in ("harmonix", "salami"):
            continue
        y, sr = librosa.load(song.audio, sr=22050, duration=120)
        rows[f"{song.set}/{song.name}"] = round(float(librosa.estimate_tuning(y=y, sr=sr)) * 100, 1)
        print(song.set, song.name, rows[f"{song.set}/{song.name}"], flush=True)
    cents = np.abs(np.array(list(rows.values())))
    result = {"songs": len(cents), "median_abs_cents": round(float(np.median(cents)), 1),
              "share_over_15": round(float(np.mean(cents > 15)), 3), "share_over_25": round(float(np.mean(cents > 25)), 3),
              "per_song": rows}
    print({k: v for k, v in result.items() if k != "per_song"})
    save_result("tuning_survey", result)


def rate(cents: float) -> float:
    return 2 ** (cents / 1200)


def render() -> None:
    import librosa
    import soundfile as sf

    WORK.mkdir(parents=True, exist_ok=True)
    estimates = {}
    for song in SONGS:
        y, sr = sf.read(Path(DATA, "score_stems", song, "mix.wav"), always_2d=True)
        y = y.mean(axis=1)
        for cents in CENTS:
            # played back `rate` times faster: resample to sr / rate and keep calling it sr
            detuned = librosa.resample(y, orig_sr=sr, target_sr=int(round(sr / rate(cents))))
            sf.write(WORK / f"{song}__{cents:+d}.wav", detuned, sr)
            est = float(librosa.estimate_tuning(y=detuned, sr=sr)) * 100
            fixed = librosa.resample(detuned, orig_sr=sr, target_sr=int(round(sr * rate(est))))
            sf.write(WORK / f"{song}__{cents:+d}_fixed.wav", fixed, sr)
            estimates[f"{song}__{cents:+d}"] = round(est, 1)
            print(song, cents, "estimated", round(est, 1), flush=True)
        sf.write(WORK / f"{song}__0.wav", y, sr)
    (WORK / "estimates.json").write_text(json.dumps(estimates, indent=1))


def jobs() -> None:
    print(" ".join(str(p) for p in sorted(WORK.glob("*.wav"))))


def evaluate() -> None:
    import pretty_midi

    from test_multitrack import FAMILIES, family, note_prf, reference

    estimates = json.loads((WORK / "estimates.json").read_text())
    result: dict[str, dict] = {}
    for variant in ["0"] + [f"{c:+d}" for c in CENTS] + [f"{c:+d}_fixed" for c in CENTS]:
        fs = []
        for song in SONGS:
            midi = WORK / "ymt3" / f"{song}__{variant}.mid"
            if not midi.exists():
                continue
            ref = reference(song)
            r = np.concatenate([ref[f] for f in FAMILIES if f in ref])
            if variant != "0":
                cents = int(variant.split("_")[0])
                scale = 1 / rate(cents)  # played faster (sharper) = shorter
                if variant.endswith("_fixed"):
                    scale *= rate(estimates[f"{song}__{cents:+d}"])
                r = r.copy()
                r[:, :2] *= scale
            est = [(n.start, n.end, n.pitch) for inst in pretty_midi.PrettyMIDI(str(midi)).instruments
                   if family(inst.program, inst.is_drum) != "drums" for n in inst.notes]
            fs.append(note_prf(r, np.array(est, dtype=float).reshape(-1, 3))[2])
        if fs:
            result[variant] = {"note_f": round(float(np.mean(fs)), 3), "songs": len(fs)}
            print(variant, result[variant])
    result["estimated_cents"] = estimates
    save_result("tuning", result)


if __name__ == "__main__":
    {"survey": survey, "render": render, "jobs": jobs, "evaluate": evaluate}[sys.argv[1]]()
