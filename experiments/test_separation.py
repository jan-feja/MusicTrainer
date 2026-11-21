"""Stem separation: quality (SDR vs ground truth) and speed.

  python test_separation.py musdb   # MUSDB18 7-second previews, 50 test tracks
  python test_separation.py synth   # synthetic song, incl. guitar & piano stems
  python test_separation.py speed <wav>  # time a full song on GPU and CPU

SDR (dB, higher is better) is the "utterance SDR" used by the Music
Demixing challenges. As a rule of thumb: <3 dB poor, 5-7 dB usable for
practice (instrument clearly audible, some bleed), >9 dB very clean.
"""
import os
import sys
import time
import warnings

import numpy as np
import soundfile as sf
import torch

from common import DATA, DEVICE, save_result, synth_dir, usdr

warnings.filterwarnings("ignore")
_models = {}


def demucs_separate(name, wav, sr, device):
    """wav: (samples, channels) float numpy at 44.1 kHz -> {stem: array}"""
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    key = (name, device)
    if key not in _models:
        m = get_model(name)
        m.to(device).eval()
        _models[key] = m
    m = _models[key]
    x = torch.tensor(wav.T, dtype=torch.float32)
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    ref = x.mean(0)
    x = (x - ref.mean()) / (ref.std() + 1e-8)
    with torch.no_grad():
        out = apply_model(m, x[None], device=device, shifts=1, split=True, overlap=0.25, progress=False)[0]
    out = out * ref.std() + ref.mean()
    return {s: out[i].cpu().numpy().T for i, s in enumerate(m.sources)}


def roformer_separate(model_file, wav, sr, device):
    """BS-/MelBand-RoFormer models via the audio-separator package."""
    from audio_separator.separator import Separator
    import tempfile
    key = (model_file, device)
    tmp = os.path.join(DATA, "sep_tmp")
    os.makedirs(tmp, exist_ok=True)
    if key not in _models:
        sep = Separator(output_dir=tmp, model_file_dir=os.path.join(DATA, "models"), log_level=40,
                        output_format="WAV")
        sep.load_model(model_filename=model_file)
        _models[key] = sep
    sep = _models[key]
    inp = os.path.join(tmp, "input.wav")
    sf.write(inp, wav, sr)
    files = sep.separate(inp)
    out = {}
    for f in files:
        f = f if os.path.isabs(f) else os.path.join(tmp, f)
        stem = f.split("(")[-1].split(")")[0].lower()
        y, _ = sf.read(f, always_2d=True)
        out[stem] = y
        os.remove(f)
    return out


MODELS = {
    "htdemucs": lambda w, sr, d: demucs_separate("htdemucs", w, sr, d),
    "htdemucs_ft": lambda w, sr, d: demucs_separate("htdemucs_ft", w, sr, d),
    "htdemucs_6s": lambda w, sr, d: demucs_separate("htdemucs_6s", w, sr, d),
    "bs_roformer_sw": lambda w, sr, d: roformer_separate("BS-Roformer-SW.ckpt", w, sr, d),
}


def score(refs, ests):
    out = {}
    for stem, ref in refs.items():
        if stem == "other" and "guitar" in ests and "guitar" not in refs:
            # 6-stem model vs 4-stem truth: other = guitar + piano + other
            out[stem] = usdr(ref, ests["guitar"] + ests.get("piano", 0) + ests["other"])
        elif stem in ests:
            out[stem] = usdr(ref, ests[stem])
    return out


def run_musdb(models):
    import musdb
    db = musdb.DB(root=os.path.join(DATA, "musdb"), download=True, subsets="test")
    res = {m: [] for m in models}
    tracks = db.tracks[: int(os.environ.get("MUSDB_N", "50"))]
    for t in tracks:
        mix = t.audio
        refs = {s: t.targets[s].audio for s in ("vocals", "drums", "bass", "other")}
        for m in models:
            ests = MODELS[m](mix, t.rate, DEVICE)
            res[m].append(score(refs, ests))
    summary = {}
    for m, rows in res.items():
        summary[m] = {s: float(np.median([r[s] for r in rows if s in r])) for s in rows[0]}
        print(f"{m:15s} median SDR over {len(rows)} tracks: " +
              "  ".join(f"{s}={v:5.2f}" for s, v in summary[m].items()))
    save_result("separation_musdb", summary, merge=True)


def run_synth(models):
    d = synth_dir("steady")
    mix, sr = sf.read(f"{d}/mix.wav", always_2d=True)
    stems = {s: sf.read(f"{d}/stems/{s}.wav", always_2d=True)[0] for s in ("drums", "bass", "guitar", "piano", "vocals")}
    stems = {k: (v if v.shape[1] == 2 else np.repeat(v, 2, 1)) for k, v in stems.items()}
    mix = mix if mix.shape[1] == 2 else np.repeat(mix, 2, 1)
    summary = {}
    for m in models:
        ests = MODELS[m](mix, sr, DEVICE)
        refs = dict(stems)
        if "guitar" not in ests:  # 4-stem model: guitar + piano land in "other"
            refs = {"drums": stems["drums"], "bass": stems["bass"], "vocals": stems["vocals"],
                    "other": stems["guitar"] + stems["piano"]}
        summary[m] = score(refs, ests)
        print(f"{m:15s} " + "  ".join(f"{s}={v:5.2f}" for s, v in summary[m].items()))
    save_result("separation_synth", summary, merge=True)


def run_speed(models, wav_path):
    wav, sr = sf.read(wav_path, always_2d=True)
    dur = len(wav) / sr
    res = {}
    for m in models:
        for dev in (os.environ.get("SPEED_DEVICES") or "cuda,cpu").split(","):
            if dev == "cpu" and m == "htdemucs_ft":
                continue  # 4x slower than htdemucs, skip on CPU
            MODELS[m](wav[: sr * 10], sr, dev)  # warm-up / model load
            if dev == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            secs = int(os.environ.get("SPEED_SECONDS", "0"))
            MODELS[m](wav[: sr * secs] if secs else wav, sr, dev)
            dur = (secs or len(wav) / sr)
            dt = time.perf_counter() - t0
            res[f"{m}/{dev}"] = dt
            print(f"{m:15s} {dev:4s} {dt:6.1f} s for {dur:.0f} s of audio ({dur / dt:.1f}x real time)")
    save_result("separation_speed", res, merge=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    models = [m for m in MODELS if m in (os.environ.get("MODELS") or ",".join(MODELS)).split(",")]
    if cmd == "musdb":
        run_musdb(models)
    elif cmd == "synth":
        run_synth(models)
    elif cmd == "speed":
        run_speed(models, sys.argv[2])
