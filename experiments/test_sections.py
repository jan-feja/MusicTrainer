"""Song section detection (intro / verse / chorus ...).

Methods:
  laplacian       librosa Laplacian segmentation (McFee & Ellis 2014) on a beat grid
  laplacian_snap  same, boundaries snapped to the nearest bar start (downbeat)
  allin1          All-In-One structure analyzer (if installed; needs Linux/WSL)
Ground truth: synthetic song + Harmonix annotations.
Metrics (mir_eval): boundary F-measure at +-0.5 s and +-3 s; pairwise F says
whether repeated sections get the same label (e.g. all choruses grouped).
"""
import warnings

import librosa
import mir_eval
import numpy as np
import scipy
import sklearn.cluster

from common import BEAT_THIS_CKPT, DEVICE, harmonix_offset, harmonix_segments, harmonix_songs, load_gt, save_result, synth_dir

warnings.filterwarnings("ignore")
_f2b = None


def beat_grid(path):
    global _f2b
    from beat_this.inference import File2Beats
    if _f2b is None:
        _f2b = File2Beats(checkpoint_path=BEAT_THIS_CKPT, device=DEVICE, dbn=False)
    b, db = _f2b(path)
    return np.asarray(b), np.asarray(db)


def laplacian(path, k=5, snap=False):
    y, sr = librosa.load(path, sr=22050)
    beats_t, downbeats_t = beat_grid(path)
    C = librosa.amplitude_to_db(np.abs(librosa.cqt(y=y, sr=sr, bins_per_octave=36, n_bins=7 * 36)), ref=np.max)
    beats = librosa.util.fix_frames(librosa.time_to_frames(beats_t, sr=sr), x_min=0)
    Csync = librosa.util.sync(C, beats, aggregate=np.median)
    R = librosa.segment.recurrence_matrix(Csync, width=3, mode="affinity", sym=True)
    Rf = librosa.segment.timelag_filter(scipy.ndimage.median_filter)(R, size=(1, 7))
    Msync = librosa.util.sync(librosa.feature.mfcc(y=y, sr=sr), beats)
    pd_ = np.sum(np.diff(Msync, axis=1) ** 2, axis=0)
    path_sim = np.exp(-pd_ / np.median(pd_))
    R_path = np.diag(path_sim, k=1) + np.diag(path_sim, k=-1)
    deg_p, deg_r = R_path.sum(1), Rf.sum(1)
    mu = deg_p.dot(deg_p + deg_r) / np.sum((deg_p + deg_r) ** 2)
    A = mu * Rf + (1 - mu) * R_path
    L = scipy.sparse.csgraph.laplacian(A, normed=True)
    _, evecs = scipy.linalg.eigh(L)
    evecs = scipy.ndimage.median_filter(evecs, size=(9, 1))
    Cnorm = np.cumsum(evecs ** 2, axis=1) ** 0.5
    X = evecs[:, :k] / (Cnorm[:, k - 1:k] + 1e-9)
    seg_ids = sklearn.cluster.KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
    bb = librosa.util.fix_frames(1 + np.flatnonzero(seg_ids[:-1] != seg_ids[1:]), x_min=0)
    labels = [str(seg_ids[i]) for i in bb]
    times = librosa.frames_to_time(beats[bb], sr=sr)
    end = len(y) / sr
    if snap and len(downbeats_t):
        times = np.array([downbeats_t[np.argmin(np.abs(downbeats_t - t))] if t > 0 else 0.0 for t in times])
    # build intervals, merging zero-length ones created by snapping
    ints, labs = [], []
    for t, lab in zip(times, labels):
        if ints and t <= ints[-1][0] + 1e-3:
            labs[-1] = lab
            continue
        if ints:
            ints[-1][1] = t
        ints.append([t, end])
        labs.append(lab)
    return np.array(ints), labs


def allin1_segments(path):
    import allin1
    r = allin1.analyze(path)
    return np.array([[s.start, s.end] for s in r.segments]), [s.label for s in r.segments]


METHODS = {"laplacian": lambda p: laplacian(p), "laplacian_snap": lambda p: laplacian(p, snap=True),
           "allin1": allin1_segments}


def evaluate(ref_i, ref_l, est_i, est_l):
    # mir_eval wants both annotations to start at 0 and end at the same time
    ref_i, ref_l = mir_eval.util.adjust_intervals(np.asarray(ref_i), list(ref_l), 0.0, None, "silence", "silence")
    est_i, est_l = mir_eval.util.adjust_intervals(np.asarray(est_i), list(est_l), 0.0, ref_i.max(), "silence", "silence")
    f05 = mir_eval.segment.detection(ref_i, est_i, window=0.5, trim=True)[2]
    f3 = mir_eval.segment.detection(ref_i, est_i, window=3.0, trim=True)[2]
    pw = mir_eval.segment.pairwise(ref_i, ref_l, est_i, est_l)[2]
    return dict(F_0_5s=f05, F_3s=f3, pairwise_F=pw, n_est=len(est_i), n_ref=len(ref_i))


def main():
    items = []
    gt = load_gt("steady")
    items.append(("synth_steady", f"{synth_dir('steady')}/mix.wav",
                  np.array([[a, b] for a, b, _ in gt["sections"]]), [l for _, _, l in gt["sections"]]))
    for sid, wav, _ in harmonix_songs():
        ints, labs = harmonix_segments(sid)
        items.append((sid, wav, ints + harmonix_offset(sid, wav), labs))
    res = {}
    for name, fn in METHODS.items():
        try:
            for sid, wav, ri, rl in items:
                r = evaluate(ri, rl, *fn(wav))
                res.setdefault(name, {})[sid] = r
                print(f"{name:15s} {sid:28s} " + " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in r.items()))
        except Exception as e:
            print(f"{name}: unavailable ({type(e).__name__}: {str(e)[:150]})")
    print("\nAverage over real songs:")
    for name, rows in res.items():
        real = [r for k, r in rows.items() if not k.startswith("synth")]
        if real:
            print(f"  {name:15s} " + " ".join(f"{k}={np.mean([r[k] for r in real]):.2f}" for k in ("F_0_5s", "F_3s", "pairwise_F")))
    save_result("sections", res)


if __name__ == "__main__":
    main()
