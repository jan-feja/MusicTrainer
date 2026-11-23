"""Which string? Let the sound decide: a TabCNN-style model + the fingering search.

The same pitch sounds different on different strings (a fretted note on a thick string is darker
than the open thin string). TabCNN (Wiggins & Kim, ISMIR 2019) learns this from GuitarSet: CQT
frames in, for each of the six strings the fret it plays (or silence) out.

Here: the same kind of network, trained on guitarists 00-04 (validation: 10 % of their excerpts),
tested on guitarist 05 like test_tablature.py / test_guitar_tabs.py. Its use for tabs: every note
(from a transcription) gets, for each place it can be played, the network's mean log-probability
over the note's first 100 ms; tablature.assign_frets adds that (times a weight tuned on 00-04) to
its playability costs.

Metrics: string accuracy on the true notes (= test_tablature.py, which reached 0.577 without
the network), and tab F from Basic Pitch / YourMT3+ notes (= test_guitar_tabs.py).

Usage: python test_string_model.py        (writes results/string_model.json; GPU recommended)
       python test_string_model.py idmt   (the same network on IDMT-SMT-Guitar's electric guitars:
                                           results/string_model_idmt.json)
       python test_string_model.py cross-guitar   (trained on GuitarSet + two IDMT electrics + Ibanez,
                                           tested on the IDMT Les Paul and GuitarSet guitarist 05)
"""

import json
from pathlib import Path

import librosa
import numpy as np
import torch
from torch import nn

import tablature as tab
from common import DATA, DEVICE, save_result
from test_guitar_tabs import basic_pitch, scores, yourmt3
from test_tablature import guitarset_notes, string_accuracy

ROOT = Path(DATA, "guitarset")
CACHE = Path(DATA, "transcription", "guitarset_cqt")
SR, HOP, BINS, PER_OCTAVE = 22050, 512, 144, 24  # 6 octaves from E2 (TabCNN: 192 bins, beyond Nyquist at 22 kHz)
CONTEXT = 9  # frames around the center frame
FRETS = 20  # classes per string: silent, fret 0 .. FRETS
FPS = SR / HOP


def features(name: str) -> np.ndarray:
    path = CACHE / f"{name}.npy"
    if not path.exists():
        y, _ = librosa.load(str(ROOT / "audio_mono-mic" / f"{name}_mic.wav"), sr=SR)
        cqt = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("E2"), n_bins=BINS, bins_per_octave=PER_OCTAVE))
        CACHE.mkdir(parents=True, exist_ok=True)
        np.save(path, librosa.amplitude_to_db(cqt, ref=np.max).astype(np.float32).T)  # (frames, bins)
    return np.load(path)


def labels(name: str, frames: int) -> np.ndarray:
    """(frames, 6): 0 = silent, 1 + fret otherwise (low E string = 0)."""
    out = np.zeros((frames, 6), dtype=np.int64)
    for onset, offset, pitch, string in guitarset_notes(ROOT / "annotation" / f"{name}.jams"):
        fret = pitch - tab.STANDARD[string]
        if 0 <= fret <= FRETS:
            out[int(onset * FPS): max(int(offset * FPS), int(onset * FPS) + 1), string] = 1 + fret
    return out


class TabCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3), nn.ReLU(), nn.Conv2d(32, 64, 3), nn.ReLU(), nn.Conv2d(64, 64, 3), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout(0.25))
        with torch.no_grad():
            n = self.conv(torch.zeros(1, 1, CONTEXT, BINS)).numel()
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(n, 128), nn.ReLU(), nn.Dropout(0.5), nn.Linear(128, 6 * (FRETS + 2)))

    def forward(self, x):  # x: (batch, CONTEXT, BINS)
        return self.head(self.conv(x[:, None])).view(-1, 6, FRETS + 2)


def windows(feat: np.ndarray) -> np.ndarray:
    pad = np.pad(feat, ((CONTEXT // 2, CONTEXT // 2), (0, 0)), constant_values=feat.min())
    return np.lib.stride_tricks.sliding_window_view(pad, CONTEXT, axis=0).transpose(0, 2, 1)


def train(names: list[str], epochs: int = 8, extra: list[tuple[np.ndarray, np.ndarray]] = ()) -> TabCNN:
    """Train on GuitarSet excerpts `names` (+ `extra` (features, labels) pairs); 10 % validation."""
    rng = np.random.default_rng(0)
    items = [(features(n), None, n) for n in names] + [(f, l, None) for f, l in extra]
    val = set(rng.choice(len(items), size=max(1, len(items) // 10), replace=False).tolist())
    def stack(idx):
        xs, ys = [], []
        for i in idx:
            f, lab, name = items[i]
            xs.append(windows(f))
            ys.append(labels(name, len(f)) if lab is None else lab)
        return np.concatenate(xs), np.concatenate(ys)
    x_tr, y_tr = stack([i for i in range(len(items)) if i not in val])
    x_va, y_va = stack(sorted(val))
    mean, std = x_tr.mean(), x_tr.std()
    model = TabCNN().to(DEVICE)
    model.norm = (float(mean), float(std))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    best = (np.inf, None)
    for epoch in range(epochs):
        model.train()
        order = rng.permutation(len(x_tr))
        for i in range(0, len(order), 256):
            idx = order[i: i + 256]
            xb = torch.from_numpy((x_tr[idx] - mean) / std).to(DEVICE)
            yb = torch.from_numpy(y_tr[idx]).to(DEVICE)
            loss = loss_fn(model(xb).reshape(-1, FRETS + 2), yb.reshape(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            losses = []
            for i in range(0, len(x_va), 2048):
                xb = torch.from_numpy((x_va[i: i + 2048] - mean) / std).to(DEVICE)
                yb = torch.from_numpy(y_va[i: i + 2048]).to(DEVICE)
                losses.append(float(loss_fn(model(xb).reshape(-1, FRETS + 2), yb.reshape(-1))))
        val_loss = float(np.mean(losses))
        print(f"epoch {epoch}: validation loss {val_loss:.4f}", flush=True)
        if val_loss < best[0]:
            best = (val_loss, {k: v.detach().clone() for k, v in model.state_dict().items()})
    model.load_state_dict(best[1])
    return model.eval()


MODEL = Path(DATA, "transcription", "tabcnn_guitarset_00-04.pt")


def load_or_train(train_names: list[str]) -> TabCNN:
    """The network trained on guitarists 00-04 (cached in MODEL)."""
    if MODEL.exists():
        state = torch.load(MODEL, map_location=DEVICE)
        model = TabCNN().to(DEVICE)
        model.load_state_dict(state["weights"])
        model.norm = tuple(state["norm"])
        return model.eval()
    model = train(train_names)
    torch.save({"weights": model.state_dict(), "norm": list(model.norm)}, MODEL)
    return model


def log_probs(model: TabCNN, name: str, feat: np.ndarray | None = None) -> np.ndarray:
    """(frames, 6, FRETS + 2) log-probabilities."""
    mean, std = model.norm
    w = windows(features(name) if feat is None else feat)
    out = []
    with torch.no_grad():
        for i in range(0, len(w), 2048):
            xb = torch.from_numpy((w[i: i + 2048] - mean) / std).to(DEVICE)
            out.append(torch.log_softmax(model(xb), dim=-1).cpu().numpy())
    return np.concatenate(out)


def audio_cost(lp: np.ndarray, weight: float):
    """A note_cost for tablature.assign_frets: -weight * mean log P(string plays fret) over 100 ms."""
    span = max(1, int(0.1 * FPS))

    def cost(onset: float, string: int, fret: int) -> float:
        a = min(int(onset * FPS), len(lp) - 1)
        if fret > FRETS:
            return 0.0
        return -weight * float(lp[a: a + span, string, 1 + fret].mean())

    return cost


def main() -> None:
    tuned = json.loads(Path(__file__).with_name("results").joinpath("tablature.json").read_text())["tuned_costs"]
    tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = tuned["move"], tuned["height"], tuned["open_bonus"]
    names = sorted(p.stem for p in (ROOT / "annotation").glob("*.jams"))
    train_names = [n for n in names if not n.startswith("05")]
    test_names = [n for n in names if n.startswith("05")]
    model = load_or_train(train_names)
    lps = {n: log_probs(model, n) for n in names}

    def with_audio(weight, name):
        return lambda notes: tab.assign_frets(notes, note_cost=audio_cost(lps[name], weight))

    def accuracy(weight, subset):
        right = total = 0
        for n in subset:
            truth = guitarset_notes(ROOT / "annotation" / f"{n}.jams")
            acc = string_accuracy(with_audio(weight, n), [truth])
            right += acc * len(truth)
            total += len(truth)
        return right / total

    tune_subset = train_names[::3]  # a third of guitarists 00-04 (the network saw them: optimistic)
    weights = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
    tune = {w: round(accuracy(w, tune_subset), 3) for w in weights}
    best = max(tune, key=tune.get)
    print("weight tuning (train):", tune, "->", best)
    result = {"weight_tuning_train": tune, "weight": best,
              "string_accuracy_test05": {"search_only": round(accuracy(0.0, test_names), 3),
                                         "network_only": round(accuracy(1000.0, test_names), 3),
                                         "search_plus_network": round(accuracy(best, test_names), 3)}}
    for method, fn in (("basic_pitch", basic_pitch), ("yourmt3", yourmt3)):
        rows = []
        for n in test_names:
            est = fn(n)
            if est is None:
                continue
            truth = guitarset_notes(ROOT / "annotation" / f"{n}.jams")
            saved = tab.assign_frets
            tab.assign_frets = lambda notes, *a, _n=n, **k: saved(notes, note_cost=audio_cost(lps[_n], best))
            try:
                rows.append(scores(truth, est))
            finally:
                tab.assign_frets = saved
        if rows:
            result[f"tab_f_{method}"] = {"tab_f": round(float(np.mean([r["tab"][2] for r in rows])), 3),
                                         "string_of_found": round(sum(r["string_ok"] for r in rows) / max(1, sum(r["matched"] for r in rows)), 3),
                                         "excerpts": len(rows)}
    print(json.dumps(result, indent=1))
    save_result("string_model", result)


def idmt_notes(xml: Path) -> list[tuple[float, float, int, int]]:
    """(onset, offset, pitch, string) of an IDMT-SMT-Guitar annotation (string 0 = low E)."""
    import xml.etree.ElementTree as ET

    out = []
    for e in ET.parse(xml).getroot().iter("event"):
        out.append((float(e.findtext("onsetSec")), float(e.findtext("offsetSec")), int(e.findtext("pitch")),
                    int(e.findtext("stringNumber")) - 1))
    return sorted(out)


def idmt_files(guitars: set[str] | None = None) -> list[tuple[Path, Path, str]]:
    """(xml, wav, group) of the usable IDMT recordings; guitars: dataset2 prefixes (AR, FS, LP) or 'Ibanez'."""
    root = Path(DATA, "idmt", "IDMT-SMT-GUITAR_V2")
    out = []
    for ds in ("dataset2", "dataset3"):
        for xml in sorted((root / ds / "annotation").glob("*.xml")):
            if any(k in xml.stem for k in ("NH_", "muted", "V_vibrato", "_DN", "dead")):
                continue
            wav = root / ds / "audio" / f"{xml.stem}.wav"
            guitar = xml.stem.split("_")[0] if ds == "dataset2" else "Ibanez"
            if wav.exists() and (guitars is None or guitar in guitars):
                kind = "scales" if "fret" in xml.stem else ("licks" if "Lick" in xml.stem else ds)
                out.append((xml, wav, f"{kind}/{guitar}"))
    return out


def idmt_features(wav: Path) -> np.ndarray:
    path = CACHE / "idmt" / f"{wav.stem}.npy"
    if not path.exists():
        y, _ = librosa.load(str(wav), sr=SR)
        cqt = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("E2"), n_bins=BINS, bins_per_octave=PER_OCTAVE))
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, librosa.amplitude_to_db(cqt, ref=np.max).astype(np.float32).T)
    return np.load(path)


def idmt_labels(xml: Path, frames: int) -> np.ndarray:
    out = np.zeros((frames, 6), dtype=np.int64)
    for onset, offset, pitch, string in idmt_notes(xml):
        fret = pitch - tab.STANDARD[string]
        if 0 <= string < 6 and 0 <= fret <= FRETS:
            out[int(onset * FPS): max(int(offset * FPS), int(onset * FPS) + 1), string] = 1 + fret
    return out


def cross_guitar() -> None:
    """Train on GuitarSet 00-04 + IDMT Aristides, Stratocaster and Ibanez; test on the IDMT Les Paul
    (held out: humbucker pickups, the most different sound) and on GuitarSet guitarist 05."""
    tuned = json.loads(Path(__file__).with_name("results").joinpath("tablature.json").read_text())["tuned_costs"]
    tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = tuned["move"], tuned["height"], tuned["open_bonus"]
    weight = json.loads(Path(__file__).with_name("results").joinpath("string_model.json").read_text())["weight"]
    names = sorted(p.stem for p in (ROOT / "annotation").glob("*.jams"))
    model_path = Path(DATA, "transcription", "tabcnn_multi_guitar.pt")
    if model_path.exists():
        state = torch.load(model_path, map_location=DEVICE)
        model = TabCNN().to(DEVICE)
        model.load_state_dict(state["weights"])
        model.norm = tuple(state["norm"])
        model.eval()
    else:
        extra = []
        for xml, wav, _ in idmt_files({"AR", "FS", "Ibanez"}):
            f = idmt_features(wav)
            extra.append((f, idmt_labels(xml, len(f))))
        model = train([n for n in names if not n.startswith("05")], extra=extra)
        torch.save({"weights": model.state_dict(), "norm": list(model.norm)}, model_path)
    result = {}
    for xml, wav, group in idmt_files({"LP"}):
        truth = idmt_notes(xml)
        if len(truth) < 3:
            continue
        lp = log_probs(model, xml.stem, idmt_features(wav))
        for method, cost in (("search_only", None), ("search_plus_network", audio_cost(lp, weight))):
            acc = string_accuracy(lambda notes, c=cost: tab.assign_frets(notes, note_cost=c), [truth])
            row = result.setdefault(f"{group}/{method}", [0.0, 0])
            row[0] += acc * len(truth)
            row[1] += len(truth)
    right = total = 0
    for n in (n for n in names if n.startswith("05")):
        truth = guitarset_notes(ROOT / "annotation" / f"{n}.jams")
        lp = log_probs(model, n)
        acc = string_accuracy(lambda notes: tab.assign_frets(notes, note_cost=audio_cost(lp, weight)), [truth])
        right += acc * len(truth)
        total += len(truth)
    out = {k: {"right_string": round(v[0] / v[1], 3), "notes": v[1]} for k, v in sorted(result.items())}
    out["guitarset_05/search_plus_network"] = {"right_string": round(right / total, 3), "notes": total}
    for k, v in out.items():
        print(k, v)
    save_result("string_model_cross_guitar", out)


def idmt() -> None:
    """Generalization: the network trained on GuitarSet (one acoustic guitar) on IDMT-SMT-Guitar's
    electric guitars (dataset2: Aristides, Stratocaster, Les Paul; scales on every string up to
    fret 20, licks played in several positions; dataset3: pieces on an Ibanez). Harmonics, muted
    notes and vibrato studies are left out."""
    tuned = json.loads(Path(__file__).with_name("results").joinpath("tablature.json").read_text())["tuned_costs"]
    tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = tuned["move"], tuned["height"], tuned["open_bonus"]
    weight = json.loads(Path(__file__).with_name("results").joinpath("string_model.json").read_text())["weight"]
    names = sorted(p.stem for p in (ROOT / "annotation").glob("*.jams"))
    model = load_or_train([n for n in names if not n.startswith("05")])
    root = Path(DATA, "idmt", "IDMT-SMT-GUITAR_V2")
    counts: dict[str, np.ndarray] = {}
    for ds in ("dataset2", "dataset3"):
        for xml in sorted((root / ds / "annotation").glob("*.xml")):
            if any(k in xml.stem for k in ("NH_", "muted", "V_vibrato", "_DN", "dead")):
                continue
            wav = root / ds / "audio" / f"{xml.stem}.wav"
            truth = idmt_notes(xml)
            if not wav.exists() or len(truth) < 3:
                continue
            y, _ = librosa.load(str(wav), sr=SR)
            cqt = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("E2"), n_bins=BINS, bins_per_octave=PER_OCTAVE))
            lp = log_probs(model, xml.stem, librosa.amplitude_to_db(cqt, ref=np.max).astype(np.float32).T)
            kind = "scales" if "fret" in xml.stem else ("licks" if "Lick" in xml.stem else ds)
            group = f"{kind}/{xml.stem.split('_')[0] if ds == 'dataset2' else 'Ibanez'}"
            for method, cost in (("search_only", None), ("search_plus_network", audio_cost(lp, weight)), ("network_only", audio_cost(lp, 1000.0))):
                acc = string_accuracy(lambda notes, c=cost: tab.assign_frets(notes, note_cost=c), [truth])
                counts.setdefault(f"{group}/{method}", np.zeros(2))
                counts[f"{group}/{method}"] += [acc * len(truth), len(truth)]
    result = {k: {"right_string": round(v[0] / v[1], 3), "notes": int(v[1])} for k, v in sorted(counts.items())}
    for k, v in result.items():
        print(k, v)
    save_result("string_model_idmt", result)


if __name__ == "__main__":
    import sys

    {"idmt": idmt, "cross-guitar": cross_guitar, "guitarset": main}[sys.argv[1] if len(sys.argv) > 1 else "guitarset"]()
