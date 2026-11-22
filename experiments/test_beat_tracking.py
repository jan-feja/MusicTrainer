"""Beat and bar tracking benchmark: decoding methods on several test sets.

Test sets (all under MT_DATA):
  score     score_songs/<name>/ from score_to_audio.py: exact answers from the score, music that
            no model has been trained on, grouped by category (odd meters, tempo changes, ...)
  synth     synth_<variant>/ from make_synth_song.py
  harmonix  real songs with human annotations. Beat This! was trained on the Harmonix Set, so these
            numbers are optimistic for the network itself; they still show what the decoding does.
  gtzan     GTZAN: 1000 real 30-second clips, 10 genres (gtzan/genres/<genre>/*.wav), annotations from
            github.com/CPJKU/beat_this_annotations (gtzan/beat_this_annotations-main/). The Beat This!
            "final" models were trained on everything except GTZAN: the honest real-music test.
  library   songs from the app library (MT_LIBRARY = data/library): no answers, only checks that need
            none (do all bars have the same number of beats?)

Metrics (70 ms tolerance):
  beat_F, down_F        F-measure of beats / bar starts
  beat_CMLt, down_CMLt  share of the song tracked continuously at the right tempo and phase;
                        drops when a tracker switches to double / half tempo or shifts the bar
  loop_<n>bar           set A on a bar start, step n bars in the detected grid: is B the right bar?
                        (extra or missing bar starts make this fail, unlike plain snapping)
  loop_4beat            the same with beats
  bias_ms, mad_ms       median timing error of matched beats and its spread
  tempo_ok, meter_ok    tempo within 4 % / most common bar length right
  odd_bars              share of detected bars whose beat count differs from the most common one

Activations (Beat This! frame logits, 50 fps) are cached per checkpoint in MT_DATA/activations/.
Usage: python test_beat_tracking.py [method ...] [--sets score,synth,harmonix,gtzan,library]
       (needs CKPT_DIR with <checkpoint>.ckpt files; missing test sets are skipped)
"""

import json
import os
import subprocess
import sys
import time
import warnings
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from common import DATA, DEVICE, harmonix_beats, harmonix_offset, harmonix_songs, save_result

warnings.filterwarnings("ignore")
SR = 22050
FPS = 50
TOLERANCE = 0.07
CKPT_DIR = Path(os.environ.get("CKPT_DIR", os.path.join(DATA, "checkpoints")))
LIBRARY = Path(os.environ.get("MT_LIBRARY", Path(__file__).resolve().parents[1] / "data" / "library"))
CACHE = Path(DATA) / "activations"
BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"


@dataclass
class Item:
    set: str
    name: str
    audio: Path
    beats: np.ndarray | None = None
    downbeats: np.ndarray | None = None
    category: str = ""
    beats_per_bar: int | None = None
    extra: dict = field(default_factory=dict)


def load_items(sets: tuple[str, ...] = ("score", "synth", "harmonix", "library")) -> list[Item]:
    items: list[Item] = []
    if "gtzan" in sets:
        annotations = Path(DATA, "gtzan", "beat_this_annotations-main", "gtzan", "annotations", "beats")
        for wav in sorted(Path(DATA, "gtzan", "genres").glob("*/*.wav")):
            genre, number = wav.stem.split(".")
            ann = annotations / f"gtzan_{genre}_{number}.beats"
            if ann.exists() and wav.stem != "jazz.00054":  # a known broken file in GTZAN
                rows = np.loadtxt(ann, ndmin=2)
                if len(rows) < 4 or rows.shape[1] < 2:  # a few clips have no bar annotations
                    continue
                downbeats = rows[rows[:, 1] == 1, 0]
                lengths = np.diff(np.flatnonzero(rows[:, 1] == 1))
                per_bar = Counter(lengths.tolist()).most_common(1)[0][0] if len(lengths) else int(rows[:, 1].max())
                items.append(Item("gtzan", wav.stem, wav, rows[:, 0], downbeats, genre, int(per_bar)))
    if "score" in sets:
        for gt_path in sorted(Path(DATA, "score_songs").glob("*/ground_truth.json")):
            gt = json.loads(gt_path.read_text())
            per_bar = Counter(m["beats_per_bar"] for m in gt["meters"]).most_common(1)[0][0]
            items.append(Item("score", gt["name"], gt_path.parent / "mix.wav", np.array(gt["beats"]),
                              np.array(gt["downbeats"]), gt["category"], per_bar))
    if "synth" in sets:
        for variant in ("steady", "live", "detune", "nodrums"):
            folder = Path(DATA, f"synth_{variant}")
            if (folder / "mix.wav").exists():
                gt = json.loads((folder / "ground_truth.json").read_text())
                items.append(Item("synth", variant, folder / "mix.wav", np.array(gt["beats"]),
                                  np.array(gt["downbeats"]), "steady" if variant != "live" else "tempo changes", 4))
    if "harmonix" in sets:
        for song_id, wav, _ in harmonix_songs():
            beats, downbeats = harmonix_beats(song_id)
            offset = harmonix_offset(song_id, wav)
            rows = np.loadtxt(os.path.join(DATA, "harmonix", "ann", f"{song_id}.beats_and_downbeats.txt"))
            per_bar = Counter(np.diff(np.flatnonzero(rows[:, 1] == 1)).tolist()).most_common(1)[0][0]
            items.append(Item("harmonix", song_id, Path(wav), beats + offset, downbeats + offset, "real", per_bar))
    if "library" in sets and LIBRARY.exists():
        for folder in sorted(LIBRARY.iterdir()):
            meta = folder / "meta.json"
            if meta.exists():
                info = json.loads(meta.read_text(encoding="utf-8"))
                if (info.get("duration_seconds") or 0) <= 900:  # skip hour-long metronome videos
                    items.append(Item("library", info.get("title", folder.name), folder / info.get("media_file", "video.mp4"),
                                      category="real (no answers)"))
    return items


# --- activations -----------------------------------------------------------------------------------

_models: dict[str, object] = {}


def decode_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def activations(item: Item, checkpoint: str = "final0") -> tuple[np.ndarray, np.ndarray]:
    """Beat and downbeat logits at 50 fps (cached)."""
    target = CACHE / checkpoint / f"{item.set}__{''.join(c if c.isalnum() else '_' for c in item.name)}.npz"
    if not target.exists():
        from beat_this.inference import Audio2Frames

        if checkpoint not in _models:
            _models[checkpoint] = Audio2Frames(str(CKPT_DIR / f"{checkpoint}.ckpt"), device=DEVICE)
        beat, down = _models[checkpoint](decode_audio(item.audio), SR)
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(target, beat=beat.cpu().numpy(), downbeat=down.cpu().numpy())
    data = np.load(target)
    return data["beat"].astype(np.float64), data["downbeat"].astype(np.float64)


# --- metrics -------------------------------------------------------------------------------------------


def _nearest(grid: np.ndarray, t: float) -> int:
    i = int(np.searchsorted(grid, t))
    if i == len(grid) or (i > 0 and abs(grid[i - 1] - t) <= abs(grid[i] - t)):
        return i - 1
    return i


def step_loop_accuracy(ref: np.ndarray, est: np.ndarray, span: int) -> float:
    """Snap A to the detected point nearest a true one, step `span` detected points: is B right too?"""
    if len(ref) <= span:
        return float("nan")
    if len(est) == 0:
        return 0.0
    ok = []
    for k in range(len(ref) - span):
        i = _nearest(est, ref[k])
        ok.append(abs(est[i] - ref[k]) < TOLERANCE and i + span < len(est) and abs(est[i + span] - ref[k + span]) < TOLERANCE)
    return float(np.mean(ok))


def odd_bar_share(beats: np.ndarray, downbeats: np.ndarray) -> tuple[float, int | None]:
    if len(downbeats) < 3:
        return float("nan"), None
    counts = np.diff(np.searchsorted(beats, downbeats - 1e-6))
    common = Counter(counts.tolist()).most_common(1)[0][0]
    return float(np.mean(counts != common)), int(common)


def evaluate(item: Item, beats: np.ndarray, downbeats: np.ndarray) -> dict:
    import mir_eval

    beats, downbeats = np.asarray(beats, dtype=float), np.asarray(downbeats, dtype=float)
    odd, per_bar = odd_bar_share(beats, downbeats)
    row = {"odd_bars": odd, "beats_per_bar": per_bar}
    if item.beats is None:
        return row
    trim = mir_eval.beat.trim_beats
    ref_b, ref_d = item.beats, item.downbeats
    # score only the annotated stretch: some YouTube versions are longer than the annotated recording
    inside = lambda t: t[(t >= ref_b[0] - TOLERANCE) & (t <= ref_b[-1] + TOLERANCE)]  # noqa: E731
    beats, downbeats = inside(beats), inside(downbeats)
    row["beat_F"] = mir_eval.beat.f_measure(trim(ref_b), trim(beats))
    row["down_F"] = mir_eval.beat.f_measure(trim(ref_d), trim(downbeats))
    row["beat_CMLt"] = mir_eval.beat.continuity(trim(ref_b), trim(beats))[1] if len(trim(beats)) > 1 else 0.0
    row["down_CMLt"] = mir_eval.beat.continuity(trim(ref_d), trim(downbeats))[1] if len(trim(downbeats)) > 1 else 0.0
    for span in (1, 2, 4):
        row[f"loop_{span}bar"] = step_loop_accuracy(ref_d, downbeats, span)
    row["loop_4beat"] = step_loop_accuracy(ref_b, beats, 4)
    errors = np.array([beats[_nearest(beats, t)] - t for t in ref_b]) if len(beats) else np.array([])
    errors = errors[np.abs(errors) < TOLERANCE]
    row["bias_ms"] = float(np.median(errors) * 1000) if len(errors) else float("nan")
    row["mad_ms"] = float(np.median(np.abs(errors - np.median(errors))) * 1000) if len(errors) else float("nan")
    est_ibi = np.median(np.diff(beats)) if len(beats) > 2 else np.inf
    row["tempo_ok"] = float(abs(est_ibi / np.median(np.diff(ref_b)) - 1) < 0.04)
    row["meter_ok"] = float(per_bar == item.beats_per_bar)
    return row


METRICS = ["beat_F", "beat_CMLt", "down_F", "down_CMLt", "loop_1bar", "loop_2bar", "loop_4bar", "loop_4beat",
           "bias_ms", "mad_ms", "tempo_ok", "meter_ok", "odd_bars"]


# --- methods -------------------------------------------------------------------------------------------

Activations = Callable[[str], tuple[np.ndarray, np.ndarray]]  # checkpoint -> (beat logits, downbeat logits)
Method = Callable[[Activations], tuple[np.ndarray, np.ndarray]]


def beat_this_minimal(acts: Activations) -> tuple[np.ndarray, np.ndarray]:
    """Beat This! default: peak picking, bar starts moved to the nearest beat (what the app used first)."""
    import torch
    from beat_this.model.postprocessor import Postprocessor

    beat, down = acts("final0")
    b, d = Postprocessor("minimal")(torch.tensor(beat), torch.tensor(down))
    return np.asarray(b), np.asarray(d)


def madmom_dbn(acts: Activations) -> tuple[np.ndarray, np.ndarray]:
    """Beat This! with madmom's DBN (3/4 and 4/4 only, one meter per song)."""
    import torch
    from beat_this.model.postprocessor import Postprocessor

    beat, down = acts("final0")
    b, d = Postprocessor("dbn")(torch.tensor(beat), torch.tensor(down))
    return np.asarray(b), np.asarray(d)


def app_decoder(checkpoints: tuple[str, ...] = ("final0",), **options) -> Method:
    """The app's decoder (backend/src/music_trainer/services/beat_decoding.py).

    `checkpoints`: average the logits of several networks; `options`: DecodingOptions fields.
    """

    def run(acts: Activations) -> tuple[np.ndarray, np.ndarray]:
        if str(BACKEND_SRC) not in sys.path:
            sys.path.insert(0, str(BACKEND_SRC))
        from music_trainer.services.beat_decoding import DecodingOptions, decode_beats

        logits = [acts(c) for c in checkpoints]
        beat = np.mean([b for b, _ in logits], axis=0)
        down = np.mean([d for _, d in logits], axis=0)
        grid = decode_beats(beat, down, DecodingOptions(**options))
        return np.asarray(grid.beats), np.asarray(grid.downbeats)

    return run


METHODS: dict[str, Method] = {
    "beat_this_minimal": beat_this_minimal,
    "madmom_dbn": madmom_dbn,
    "app": app_decoder(),
    "app_ensemble": app_decoder(("final0", "final1", "final2")),
}


# --- running ---------------------------------------------------------------------------------------------


def run(methods: dict[str, Method], items: list[Item], verbose: bool = True) -> dict:
    results: dict = {}
    for item in items:
        acts = lambda checkpoint, item=item: activations(item, checkpoint)  # noqa: E731
        for name, method in methods.items():
            t0 = time.perf_counter()
            beats, downbeats = method(acts)
            row = evaluate(item, beats, downbeats)
            row["seconds"] = time.perf_counter() - t0
            results.setdefault(name, {})[f"{item.set}/{item.name}"] = row
        if verbose:
            print(f"{item.set:8s} {item.name[:30]:30s} " + "  ".join(
                f"{n}: dF={results[n][f'{item.set}/{item.name}'].get('down_F', float('nan')):.2f} "
                f"odd={results[n][f'{item.set}/{item.name}']['odd_bars']:.2f}" for n in methods), flush=True)
    return results


def summarize(results: dict, items: list[Item], group_by: str = "set") -> dict:
    """Mean of every metric per method and group (set, or category within the score set)."""
    groups: dict[str, list[str]] = {}
    for item in items:
        key = item.set if group_by == "set" else f"{item.set}:{item.category}"
        groups.setdefault(key, []).append(f"{item.set}/{item.name}")
    summary: dict = {}
    for method, rows in results.items():
        for group, keys in groups.items():
            summary.setdefault(group, {})[method] = {
                m: float(np.nanmean([rows[k][m] for k in keys if m in rows[k]])) if any(m in rows[k] for k in keys) else float("nan")
                for m in METRICS + ["seconds"]
            }
    return summary


def print_summary(summary: dict, metrics: list[str] = METRICS) -> None:
    for group, methods in summary.items():
        print(f"\n{group}")
        print(f"{'method':28s}" + "".join(f"{m[:9]:>10s}" for m in metrics))
        for method, values in methods.items():
            print(f"{method[:28]:28s}" + "".join(f"{values[m]:10.3f}" for m in metrics))


ALL_SETS = ("score", "synth", "harmonix", "gtzan", "library")


def main() -> None:
    args = sys.argv[1:]
    sets = ALL_SETS
    if "--sets" in args:
        at = args.index("--sets")
        sets = tuple(args[at + 1].split(","))
        args = args[:at] + args[at + 2 :]
    chosen = args or list(METHODS)
    items = load_items(sets)
    results = run({m: METHODS[m] for m in chosen}, items, verbose=False)
    by_set = summarize(results, items, "set")
    by_category = summarize(results, [i for i in items if i.set in ("score", "gtzan")], "category")
    print_summary(by_set)
    print_summary(by_category, ["beat_F", "down_F", "down_CMLt", "loop_1bar", "loop_4bar", "meter_ok"])
    # per-song rows except GTZAN's 1000 clips (its summaries are kept)
    per_song = {m: {k: r for k, r in rows.items() if not k.startswith("gtzan/")} for m, rows in results.items()}
    save_result("beat_tracking", {"by_set": by_set, "by_category": by_category, "per_song": per_song})


if __name__ == "__main__":
    main()
