"""Beat, downbeat and BPM detection: librosa vs Beat This! vs madmom.

Ground truth: synthetic songs (exact) and Harmonix Set annotations for real
songs downloaded from YouTube. Metrics from mir_eval:
  F       beat F-measure, +-70 ms window (standard)
  AMLt    continuity, accepts double/half tempo and off-beat
  DB-F    downbeat F-measure (bar starts, needed for bar-snapped loops)
  BPM ok  estimated BPM within 4 % of the truth
"""
import sys
import time
import warnings

import librosa
import mir_eval
import numpy as np

import os

from common import BEAT_THIS_CKPT, DEVICE, harmonix_beats, harmonix_offset, harmonix_songs, load_gt, save_result, synth_dir

warnings.filterwarnings("ignore")


def run_librosa(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    return beats, None


_f2b = {}


def run_beat_this(path, dbn=False):
    from beat_this.inference import File2Beats
    key = (DEVICE, dbn)
    if key not in _f2b:
        _f2b[key] = File2Beats(checkpoint_path=BEAT_THIS_CKPT, device=DEVICE, dbn=dbn)
    beats, downbeats = _f2b[key](path)
    return np.asarray(beats), np.asarray(downbeats)


def run_madmom(path):
    from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor
    act = RNNDownBeatProcessor()(path)
    res = DBNDownBeatTrackingProcessor(beats_per_bar=[3, 4], fps=100)(act)
    return res[:, 0], res[res[:, 1] == 1, 0]


METHODS = {"librosa": run_librosa, "beat_this": run_beat_this, "madmom": run_madmom}
if os.environ.get("METHODS"):
    METHODS = {k: v for k, v in METHODS.items() if k in os.environ["METHODS"].split(",")}


def bpm_of(beats):
    return 60.0 / np.median(np.diff(beats)) if len(beats) > 2 else 0.0


def evaluate(ref_b, ref_db, est_b, est_db):
    ref_b, est_b = mir_eval.beat.trim_beats(np.asarray(ref_b)), mir_eval.beat.trim_beats(np.asarray(est_b))
    out = {"F": mir_eval.beat.f_measure(ref_b, est_b)}
    out["AMLt"] = mir_eval.beat.continuity(ref_b, est_b)[3]
    if est_db is not None and len(est_db) > 1:
        out["DB-F"] = mir_eval.beat.f_measure(mir_eval.beat.trim_beats(np.asarray(ref_db)),
                                              mir_eval.beat.trim_beats(np.asarray(est_db)))
    rb, eb = bpm_of(ref_b), bpm_of(est_b)
    out["BPM_ref"], out["BPM_est"] = rb, eb
    out["BPM_ok"] = abs(eb - rb) / rb < 0.04
    out["BPM_ok_x2"] = any(abs(eb * m - rb) / rb < 0.04 for m in (1, 2, 0.5, 3, 1 / 3))
    return out


def main():
    items = []
    for v in ("steady", "live"):
        gt = load_gt(v)
        items.append((f"synth_{v}", f"{synth_dir(v)}/mix.wav", gt["beats"], gt["downbeats"], 0.0))
    for sid, wav, meta in harmonix_songs():
        b, db = harmonix_beats(sid)
        off = harmonix_offset(sid, wav)
        items.append((sid, wav, b + off, db + off, off))

    results = {}
    for name, fn in METHODS.items():
        try:
            fn(items[0][1])  # warm-up (model loading) not counted
        except Exception as e:  # library not installed / broken
            print(f"{name}: unavailable ({type(e).__name__}: {e})")
            continue
        for sid, wav, rb, rdb, off in items:
            t0 = time.perf_counter()
            eb, edb = fn(wav)
            dt = time.perf_counter() - t0
            r = evaluate(rb, rdb, eb, edb)
            r["seconds"] = dt
            results.setdefault(name, {})[sid] = r
            print(f"{name:10s} {sid:28s} F={r['F']:.3f} AMLt={r['AMLt']:.3f} "
                  f"DB-F={r.get('DB-F', float('nan')):.3f} BPM {r['BPM_est']:.1f}/{r['BPM_ref']:.1f} "
                  f"({dt:.1f}s, offset {off:+.3f})")

    print("\nAverages over real songs (Harmonix):")
    for name, res in results.items():
        real = [r for k, r in res.items() if not k.startswith("synth")]
        avg = lambda key: np.mean([r[key] for r in real if key in r]) if any(key in r for r in real) else float("nan")
        print(f"  {name:10s} F={avg('F'):.3f} AMLt={avg('AMLt'):.3f} DB-F={avg('DB-F'):.3f} "
              f"BPM ok={avg('BPM_ok'):.2f} (x2 ok={avg('BPM_ok_x2'):.2f}) time/song={avg('seconds'):.1f}s")
    save_result("beats_" + "_".join(METHODS), results)


if __name__ == "__main__":
    main()
