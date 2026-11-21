"""Offline speed change (time-stretch) and pitch shift in Python.

Checks, for each library:
  - how long it takes to render 6 stems of a 2-minute song at 0.75x speed
    (relevant if the app pre-renders audio instead of stretching live)
  - that the output length is right and the pitch stays the same
  - that pitch shift moves the pitch by exactly the requested amount
Writes short examples to MT_DATA/stretch_out/ for listening.
"""
import os
import time
import warnings

import librosa
import numpy as np
import soundfile as sf

from common import DATA, save_result, synth_dir

warnings.filterwarnings("ignore")
OUT = os.path.join(DATA, "stretch_out")
os.makedirs(OUT, exist_ok=True)


def pedalboard_stretch(y, sr, rate, semitones=0.0):
    from pedalboard import time_stretch
    # pedalboard: stretch_factor > 1 = faster
    return time_stretch(y.T.astype(np.float32), sr, stretch_factor=rate,
                        pitch_shift_in_semitones=semitones, high_quality=True).T


def librosa_stretch(y, sr, rate, semitones=0.0):
    out = np.stack([librosa.effects.time_stretch(y[:, c], rate=rate) for c in range(y.shape[1])], 1)
    if semitones:
        out = np.stack([librosa.effects.pitch_shift(out[:, c], sr=sr, n_steps=semitones) for c in range(out.shape[1])], 1)
    return out


METHODS = {"pedalboard (Rubber Band)": pedalboard_stretch, "librosa (phase vocoder)": librosa_stretch}


def median_pitch_hz(y, sr):
    f0, voiced, _ = librosa.pyin(librosa.to_mono(y.T)[: sr * 20], fmin=30, fmax=400, sr=sr, frame_length=4096)
    return float(np.nanmedian(f0[voiced])) if np.any(voiced) else float("nan")


def main():
    d = synth_dir("steady")
    stems = {}
    for s in ("drums", "bass", "guitar", "piano", "vocals"):
        y, sr = sf.read(f"{d}/stems/{s}.wav", always_2d=True)
        stems[s] = y
    stems["other"] = stems["piano"] * 0.0  # 6th stem (silent) to match a 6-stem layout
    dur = len(stems["bass"]) / sr
    res = {}
    for name, fn in METHODS.items():
        t0 = time.perf_counter()
        out = {s: fn(y, sr, 0.75) for s, y in stems.items()}
        dt = time.perf_counter() - t0
        exp_len = len(stems["bass"]) / 0.75
        len_err = abs(len(out["bass"]) - exp_len) / exp_len
        p_in, p_out = median_pitch_hz(stems["bass"], sr), median_pitch_hz(out["bass"], sr)
        cents = 1200 * np.log2(p_out / p_in)
        # pitch shift +2 semitones at normal speed
        t1 = time.perf_counter()
        shifted = fn(stems["bass"], sr, 1.0, 2.0)
        dt_ps = time.perf_counter() - t1
        cents_ps = 1200 * np.log2(median_pitch_hz(shifted, sr) / p_in)
        res[name] = dict(seconds_6_stems=dt, song_seconds=dur, length_error=len_err,
                         pitch_change_cents_at_075=cents, pitch_shift_plus2_cents=cents_ps,
                         seconds_pitch_shift_1_stem=dt_ps)
        print(f"{name:26s} 6 stems x {dur:.0f}s at 0.75x: {dt:6.1f}s | length err {len_err * 100:.2f}% | "
              f"pitch drift {cents:+.1f} cents | +2 st shift -> {cents_ps:+.0f} cents ({dt_ps:.1f}s)")
        mix = sum(out.values())
        tag = name.split()[0]
        sf.write(os.path.join(OUT, f"mix_075_{tag}.wav"), mix[: int(sr * 30)], sr)
    save_result("stretch_offline", res)


if __name__ == "__main__":
    main()
