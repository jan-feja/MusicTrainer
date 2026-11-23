"""Song sections (intro, verse, chorus, solo, ...): how close do the models get?

Test sets and metrics: structure_common.py (Harmonix: optimistic, in the models' training
data; SALAMI Internet Archive: live recordings of many genres that no model saw; score songs).

Methods (each writes MT_DATA/structure/outputs/<method>/<set>__<name>.json):
  songformer   SongFormer (ASLP-lab 2025): MuQ + MusicFM embeddings, boundaries and 7 labels;
               run in WSL by the commands in experiments/README.md
  allin1       All-In-One (Kim & Nam 2023): Demucs stems + dilated neighborhood attention;
               boundaries and labels (run in WSL: python test_structure.py allin1; see allin1())
  laplacian    librosa Laplacian segmentation (McFee & Ellis 2014) on Beat This! beats, k = 5:
               boundaries and repeated parts only, no section names
  annotator2   SALAMI's second annotator scored against the first (where there is one):
               how much two people agree, a ceiling for every method
Post-processing (method name + "+bars"): every boundary moved to the nearest bar start
(Beat This! downbeats) when one is within 2 s, as the app would show it.

Usage:
  python test_structure.py beats        Beat This! beats and bar starts of every song (cache)
  python test_structure.py laplacian
  python test_structure.py allin1       (WSL venv with allin1)
  python test_structure.py evaluate     writes results/structure.json
"""

import json
import sys
from pathlib import Path

import numpy as np

import structure_common as sc
from common import BEAT_THIS_CKPT, DATA, DEVICE, save_result

BEATS = Path(DATA, "structure", "beats")
SNAP_WINDOW = 2.0


def beat_file(song: sc.Song) -> Path:
    return BEATS / f"{song.set}__{song.name}.json"


def compute_beats() -> None:
    from beat_this.inference import File2Beats

    f2b = File2Beats(checkpoint_path=BEAT_THIS_CKPT, device=DEVICE, dbn=False)
    BEATS.mkdir(parents=True, exist_ok=True)
    for song in sc.load_manifest():
        if beat_file(song).exists():
            continue
        beats, downbeats = f2b(song.audio)
        beat_file(song).write_text(json.dumps({"beats": [float(b) for b in beats], "downbeats": [float(d) for d in downbeats]}))
        print("beats", song.set, song.name, flush=True)


def load_beats(song: sc.Song) -> tuple[np.ndarray, np.ndarray] | None:
    if not beat_file(song).exists():
        return None
    data = json.loads(beat_file(song).read_text())
    return np.array(data["beats"]), np.array(data["downbeats"])


def write_output(method: str, song: sc.Song, starts, labels, end: float) -> None:
    path = sc.output_path(method, song)
    path.parent.mkdir(parents=True, exist_ok=True)
    edges = list(starts) + [end]
    path.write_text(json.dumps([{"start": float(a), "end": float(b), "label": str(l)}
                                for a, b, l in zip(edges[:-1], edges[1:], labels)]))


def laplacian() -> None:
    import librosa
    import scipy
    import sklearn.cluster

    for song in sc.load_manifest():
        if sc.output_path("laplacian", song).exists():
            continue
        grid = load_beats(song)
        if grid is None or len(grid[0]) < 16:
            continue
        y, sr = librosa.load(song.audio, sr=22050)
        cqt = librosa.amplitude_to_db(np.abs(librosa.cqt(y=y, sr=sr, bins_per_octave=36, n_bins=7 * 36)), ref=np.max)
        beats = librosa.util.fix_frames(librosa.time_to_frames(grid[0], sr=sr), x_min=0)
        csync = librosa.util.sync(cqt, beats, aggregate=np.median)
        rec = librosa.segment.recurrence_matrix(csync, width=3, mode="affinity", sym=True)
        rec = librosa.segment.timelag_filter(scipy.ndimage.median_filter)(rec, size=(1, 7))
        msync = librosa.util.sync(librosa.feature.mfcc(y=y, sr=sr), beats)
        dist = np.sum(np.diff(msync, axis=1) ** 2, axis=0)
        path_sim = np.exp(-dist / np.median(dist))
        r_path = np.diag(path_sim, k=1) + np.diag(path_sim, k=-1)
        deg_p, deg_r = r_path.sum(1), rec.sum(1)
        mu = deg_p.dot(deg_p + deg_r) / np.sum((deg_p + deg_r) ** 2)
        lap = scipy.sparse.csgraph.laplacian(mu * rec + (1 - mu) * r_path, normed=True)
        _, evecs = scipy.linalg.eigh(lap)
        evecs = scipy.ndimage.median_filter(evecs, size=(9, 1))
        k = 5
        cnorm = np.cumsum(evecs**2, axis=1) ** 0.5
        ids = sklearn.cluster.KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(evecs[:, :k] / (cnorm[:, k - 1 : k] + 1e-9))
        bounds = librosa.util.fix_frames(1 + np.flatnonzero(ids[:-1] != ids[1:]), x_min=0)
        times = librosa.frames_to_time(beats[bounds], sr=sr)
        times[0] = 0.0
        write_output("laplacian", song, times, [f"part{ids[b]}" for b in bounds], len(y) / sr)
        print("laplacian", song.set, song.name, flush=True)


def allin1() -> None:
    """Linux / WSL only (NATTEN). Demucs runs on MT_DEVICE; the structure model on ALLIN1_DEVICE
    (default cpu: NATTEN built without CUDA works there)."""
    import os

    import allin1 as a1
    from allin1.demix import demix

    work = Path(os.environ.get("ALLIN1_WORK", Path.home() / "allin1_work"))
    links = work / "in"
    links.mkdir(parents=True, exist_ok=True)
    todo = []
    for song in sc.load_manifest():
        if sc.output_path("allin1", song).exists():
            continue
        audio = song.audio
        if audio[1] == ":":  # Windows path in the manifest
            audio = "/mnt/" + audio[0].lower() + audio[2:].replace("\\", "/")
        link = links / f"{song.set}__{song.name}{Path(audio).suffix}"  # unique names for allin1's caches
        if not link.exists():
            link.symlink_to(audio)
        todo.append((song, link))
    if not todo:
        return
    demix([link for _, link in todo], work / "demix", DEVICE)
    for song, link in todo:
        r = a1.analyze(link, device=os.environ.get("ALLIN1_DEVICE", "cpu"), demix_dir=work / "demix",
                       spec_dir=work / "spec", keep_byproducts=True, multiprocess=False)
        segs = [seg for seg in r.segments if seg.end > seg.start]
        write_output("allin1", song, [seg.start for seg in segs], [seg.label for seg in segs], segs[-1].end)
        print("allin1", song.set, song.name, flush=True)


def snap_to_bars(starts, labels, downbeats, window=SNAP_WINDOW):
    """Boundaries moved to the nearest bar start within `window` s; segments that vanish are dropped."""
    out_s, out_l = [], []
    for t, lab in zip(starts, labels):
        if t > 0 and len(downbeats):
            d = downbeats[np.argmin(np.abs(downbeats - t))]
            t = float(d) if abs(d - t) <= window else t
        if out_s and t <= out_s[-1] + 1e-3:
            out_l[-1] = lab  # the earlier segment vanished
            continue
        out_s.append(t)
        out_l.append(lab)
    return out_s, out_l


def evaluate() -> None:
    songs = sc.load_manifest()
    methods = sorted(p.name for p in sc.OUTPUTS.iterdir() if p.is_dir()) if sc.OUTPUTS.exists() else []
    rows: dict[str, dict] = {}
    for method in methods:
        functional = method != "laplacian"
        for snap in (False, True):
            name = method + ("+bars" if snap else "")
            for song in songs:
                est = sc.read_output(method, song)
                if est is None:
                    continue
                starts, labels, end = est
                if snap:
                    grid = load_beats(song)
                    if grid is None:
                        continue
                    starts, labels = snap_to_bars(starts, labels, grid[1])
                rows.setdefault(name, {})[f"{song.set}/{song.name}"] = sc.evaluate(
                    (song.starts, song.labels, song.end), (starts, labels, end), functional=functional)
    for song in songs:  # human agreement
        if song.labels2:
            rows.setdefault("annotator2", {})[f"{song.set}/{song.name}"] = sc.evaluate(
                (song.starts, song.labels, song.end), (song.starts2, song.labels2, song.end))
    confusion = {name: label_confusion(name.split("+")[0], [s for s in songs if s.set == "salami"])
                 for name in rows if name in ("songformer", "allin1")}
    summary = {name: sc.summarize(r) for name, r in rows.items()}
    # the same songs for every method where possible: SALAMI songs with a second annotation
    two = {f"salami/{s.name}" for s in songs if s.labels2}
    summary_two = {name: sc.summarize({k: v for k, v in r.items() if k in two}) for name, r in rows.items()}
    for name, s in summary.items():
        print(f"{name:18s}", json.dumps(s))
    save_result("structure", {"summary": summary, "salami_two_annotators": summary_two,
                              "salami_confusion": confusion, "per_song": rows})


def label_confusion(method: str, songs: list) -> dict:
    """Share of each true class's time given each estimated class (10 Hz frames)."""
    counts = {c: dict.fromkeys(sc.CLASSES, 0) for c in sc.CLASSES}
    for song in songs:
        est = sc.read_output(method, song)
        if est is None:
            continue
        times = np.arange(0, song.end, 0.1)
        def at(starts, labels):
            idx = np.clip(np.searchsorted(np.array(starts), times, side="right") - 1, 0, len(labels) - 1)
            return [sc.map_label(labels[i]) for i in idx]
        for r, e in zip(at(song.starts, song.labels), at(est[0], est[1])):
            counts[r][e] += 1
    return {r: {e: round(n / max(1, sum(row.values())), 2) for e, n in row.items() if n} for r, row in counts.items()}


if __name__ == "__main__":
    {"beats": compute_beats, "laplacian": laplacian, "allin1": allin1, "evaluate": evaluate}[sys.argv[1]]()
