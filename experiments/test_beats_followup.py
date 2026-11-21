"""Follow-up on beat tracking, focused on what beat-synced loops need.

1. final0 (78 MB) vs small0 (8 MB) Beat This! model: accuracy and CPU speed.
2. Precision of the beat times (bias and spread), against exact ground truth.
3. A song without drums (synthetic song with the drum track removed).
4. Audio decoded from an AAC file like the app downloads vs the WAV.
5. Loops: snap 1-, 2- and 4-bar loops to the detected bar starts (or both
   ends to the nearest beat) and check that both ends land within 70 ms of
   the true bar lines / beats.

Usage: python test_beats_followup.py   (needs MT_DATA, CKPT_DIR with final0.ckpt and small0.ckpt)
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import warnings

import mir_eval
import numpy as np
import soundfile as sf

from common import (
    DATA,
    harmonix_beats,
    harmonix_offset,
    harmonix_songs,
    load_gt,
    save_result,
    synth_dir,
)

warnings.filterwarnings("ignore")
SR = 22050
TOLERANCE = 0.07  # s, the standard beat-tracking window
CKPT_DIR = os.environ["CKPT_DIR"]
MODELS = ("final0", "small0")


def decode(path: str) -> np.ndarray:
    """Mono float32 at 22.05 kHz via ffmpeg, the way the app reads its downloads."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


_trackers = {}


def track(model: str, signal: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    from beat_this.inference import Audio2Beats

    if model not in _trackers:
        _trackers[model] = Audio2Beats(
            checkpoint_path=os.path.join(CKPT_DIR, f"{model}.ckpt"), device="cpu", dbn=False
        )
        _trackers[model](signal[: SR * 5], SR)  # warm-up
    t0 = time.perf_counter()
    beats, downbeats = _trackers[model](signal, SR)
    return np.asarray(beats), np.asarray(downbeats), time.perf_counter() - t0


def timing_errors(ref: np.ndarray, est: np.ndarray) -> np.ndarray:
    """Signed error (est - ref) of every reference beat that has a detection within the window."""
    if len(est) == 0:
        return np.array([])
    idx = np.clip(np.searchsorted(est, ref), 1, len(est) - 1)
    nearest = np.where(np.abs(est[idx - 1] - ref) < np.abs(est[idx] - ref), est[idx - 1], est[idx])
    err = nearest - ref
    return err[np.abs(err) < TOLERANCE]


def snap(grid: np.ndarray, t: float) -> float:
    return float(grid[np.argmin(np.abs(grid - t))]) if len(grid) else float("nan")


def loop_accuracy(ref_grid: np.ndarray, est_grid: np.ndarray, span: int) -> float:
    """Share of loops spanning `span` grid steps whose both ends snap to the right place."""
    ok = [
        abs(snap(est_grid, ref_grid[k]) - ref_grid[k]) < TOLERANCE
        and abs(snap(est_grid, ref_grid[k + span]) - ref_grid[k + span]) < TOLERANCE
        for k in range(len(ref_grid) - span)
    ]
    return float(np.mean(ok)) if ok else float("nan")


def evaluate(ref_b, ref_db, est_b, est_db) -> dict:
    ref_b, ref_db = np.asarray(ref_b), np.asarray(ref_db)
    trimmed = lambda x: mir_eval.beat.trim_beats(np.asarray(x))  # noqa: E731
    err = timing_errors(ref_b[ref_b > 5], est_b)
    bpm_ref = 60 / np.median(np.diff(ref_b))
    bpm_est = 60 / np.median(np.diff(est_b)) if len(est_b) > 2 else 0.0
    return {
        "beat_F": mir_eval.beat.f_measure(trimmed(ref_b), trimmed(est_b)),
        "downbeat_F": mir_eval.beat.f_measure(trimmed(ref_db), trimmed(est_db)),
        "bpm_ok": abs(bpm_est - bpm_ref) / bpm_ref < 0.04,
        "bias_ms": float(np.median(err) * 1000) if len(err) else float("nan"),
        "spread_ms": float(np.median(np.abs(err - np.median(err))) * 1000) if len(err) else float("nan"),
        "loop_1bar": loop_accuracy(ref_db, est_db, 1),
        "loop_2bar": loop_accuracy(ref_db, est_db, 2),
        "loop_4bar": loop_accuracy(ref_db, est_db, 4),
        "loop_4beat_on_beats": loop_accuracy(ref_b, est_b, 4),
    }


def make_nodrums_variant() -> str:
    """The steady synthetic song without its drum track (same ground truth)."""
    target = synth_dir("nodrums")
    if not os.path.exists(os.path.join(target, "mix.wav")):
        os.makedirs(target, exist_ok=True)
        src = synth_dir("steady")
        mix = sum(sf.read(f"{src}/stems/{s}.wav")[0] for s in ("bass", "guitar", "piano", "vocals"))
        sf.write(os.path.join(target, "mix.wav"), mix / np.abs(mix).max() * 0.9, 44100)
        shutil.copy(os.path.join(src, "ground_truth.json"), target)
    return target


def main() -> None:
    make_nodrums_variant()
    items = []
    for variant in ("steady", "live", "detune", "nodrums"):
        gt = load_gt(variant)
        items.append((f"synth_{variant}", f"{synth_dir(variant)}/mix.wav", gt["beats"], gt["downbeats"]))
    for song_id, wav, _ in harmonix_songs():
        beats, downbeats = harmonix_beats(song_id)
        offset = harmonix_offset(song_id, wav)
        items.append((song_id, wav, beats + offset, downbeats + offset))

    results: dict = {}
    for model in MODELS:
        for name, path, ref_b, ref_db in items:
            signal = decode(path)
            est_b, est_db, seconds = track(model, signal)
            row = evaluate(ref_b, ref_db, est_b, est_db)
            row["cpu_seconds_per_minute"] = seconds / (len(signal) / SR / 60)
            results.setdefault(model, {})[name] = row
            print(
                f"{model} {name:28s} beatF={row['beat_F']:.3f} dbF={row['downbeat_F']:.3f} "
                f"bias={row['bias_ms']:+5.1f}ms spread={row['spread_ms']:4.1f}ms "
                f"loops 1/2/4 bars={row['loop_1bar']:.2f}/{row['loop_2bar']:.2f}/{row['loop_4bar']:.2f} "
                f"4-beat={row['loop_4beat_on_beats']:.2f} cpu={row['cpu_seconds_per_minute']:.1f}s/min"
            )

    # 4. AAC (what the app stores) vs WAV for one real song
    song_id, wav, _ = harmonix_songs()[0]
    with tempfile.TemporaryDirectory() as tmp:
        m4a = os.path.join(tmp, "audio.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-c:a", "aac", "-b:a", "128k", m4a], check=True)
        b_wav, _, _ = track("final0", decode(wav))
        b_aac, _, _ = track("final0", decode(m4a))
    n = min(len(b_wav), len(b_aac))
    results["aac_vs_wav"] = {
        "song": song_id,
        "beats_wav": len(b_wav),
        "beats_aac": len(b_aac),
        "median_abs_diff_ms": float(np.median(np.abs(b_wav[:n] - b_aac[:n])) * 1000),
    }
    print("AAC vs WAV:", json.dumps(results["aac_vs_wav"]))

    print("\nAverages:")
    for model in MODELS:
        for group, keep in (("synthetic", lambda k: k.startswith("synth")), ("real", lambda k: not k.startswith("synth"))):
            rows = [r for k, r in results[model].items() if keep(k)]
            avg = {k: float(np.nanmean([r[k] for r in rows])) for k in rows[0]}
            results[model][f"average_{group}"] = avg
            print(f"  {model} {group:9s} " + " ".join(f"{k}={v:.3f}" for k, v in avg.items()))
    save_result("beats_followup", results)


if __name__ == "__main__":
    main()
