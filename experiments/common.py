"""Shared helpers for the experiments.

Data lives outside the repo, in the folder named by the MT_DATA env var:
  MT_DATA/synth_<variant>/   output of make_synth_song.py
  MT_DATA/songs/<id>.wav     real songs downloaded with yt-dlp
  MT_DATA/harmonix/ann/      Harmonix Set annotations for those songs
"""
import json
import os
import time
from contextlib import contextmanager

import numpy as np

DATA = os.environ.get("MT_DATA", os.path.join(os.path.dirname(__file__), "data"))
# "cuda" or "cpu" for the neural models (beat_this, demucs, ADTOF)
DEVICE = os.environ.get("MT_DEVICE", "cuda")
# Beat This! weights: "final0" downloads from JKU; a local .ckpt path also works
BEAT_THIS_CKPT = os.environ.get("BEAT_THIS_CKPT", "final0")
RESULTS = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS, exist_ok=True)


def synth_dir(variant="steady"):
    return os.path.join(DATA, f"synth_{variant}")


def load_gt(variant="steady"):
    with open(os.path.join(synth_dir(variant), "ground_truth.json")) as f:
        return json.load(f)


def harmonix_songs():
    """List of (song_id, wav_path) for downloaded Harmonix songs."""
    sel = json.load(open(os.path.join(DATA, "harmonix", "selection.json")))
    out = []
    for s in sel:
        wav = os.path.join(DATA, "songs", s["file"] + ".wav")
        if os.path.exists(wav):
            out.append((s["file"], wav, s))
    return out


def harmonix_beats(song_id):
    """Annotated beats and downbeats (seconds, annotation time base)."""
    rows = np.loadtxt(os.path.join(DATA, "harmonix", "ann", f"{song_id}.beats_and_downbeats.txt"))
    beats = rows[:, 0]
    downbeats = rows[rows[:, 1] == 1, 0]
    return beats, downbeats


def harmonix_segments(song_id):
    rows = [l.split() for l in open(os.path.join(DATA, "harmonix", "ann", f"{song_id}.segments.txt")) if l.strip()]
    t = [float(r[0]) for r in rows]
    labels = [r[1] for r in rows]
    # intervals [start, end) with labels, dropping the final 'end' marker
    return np.array([[t[i], t[i + 1]] for i in range(len(t) - 1)]), labels[:-1]


_offset_cache = {}


def harmonix_offset(song_id, wav):
    """Estimate the time shift between the YouTube audio and the annotations.

    The Harmonix annotations were made on CD audio; YouTube versions can start
    a bit earlier or later. Beats repeat, so matching beats to onsets alone can
    lock onto the wrong beat (beats still match, bars do not). So:
      1. coarse: the first annotated beat is where the music starts, so line
         it up with the first clearly audible sound in the YouTube audio;
      2. fine: within +-0.45 beat of that, pick the shift that puts the
         annotated beats on the strongest onsets.
    None of the beat trackers being compared is used here.
    """
    if song_id in _offset_cache:
        return _offset_cache[song_id]
    import librosa
    y, sr = librosa.load(wav, sr=22050, mono=True)
    hop = 220  # 10 ms
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    env = env / (env.max() + 1e-9)
    beats, _ = harmonix_beats(song_id)
    rms = librosa.feature.rms(y=y[: sr * 30], hop_length=hop)[0]
    audio_start = np.argmax(rms > 0.05 * rms.max()) * hop / sr
    coarse = audio_start - beats[0]
    half = 0.45 * float(np.median(np.diff(beats)))
    best, best_d = -1, coarse
    for d in np.arange(coarse - half, coarse + half, 0.005):
        idx = np.round((beats + d) * sr / hop).astype(int)
        idx = idx[(idx >= 0) & (idx < len(env))]
        # small window max so +-10 ms annotation jitter does not matter
        s = np.mean([env[max(0, i - 1): i + 2].max() for i in idx])
        if s > best:
            best, best_d = s, d
    # 3. bar phase: YouTube versions sometimes have a few extra/missing beats at
    #    the start, which keeps beats aligned but shifts the bars. Chords mostly
    #    change at bar starts, so shift the grid by whole beats until the
    #    annotated downbeats sit where the harmony changes most.
    rows = np.loadtxt(os.path.join(DATA, "harmonix", "ann", f"{song_id}.beats_and_downbeats.txt"))
    bpb = int(rows[:, 1].max())  # beats per bar
    period = float(np.median(np.diff(beats)))
    bt = beats + best_d
    keep = (bt > 0.05) & (bt < len(y) / sr - 0.05)
    chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=512)
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    frames = librosa.time_to_frames(bt[keep], sr=sr, hop_length=512)
    # mean chroma of each beat span [beat_i, beat_i+1)
    spans = [chroma[:, a:b].mean(1) for a, b in zip(frames[:-1], frames[1:]) if b > a]
    spans = np.array([s / (np.linalg.norm(s) + 1e-9) for s in spans])
    change = 1 - np.sum(spans[1:] * spans[:-1], axis=1)  # change entering beat i+1
    beat_idx = np.flatnonzero(keep)[1:len(change) + 1]
    downbeat_flags = rows[:, 1] == 1
    scores = []
    for k in range(-(bpb // 2), bpb - bpb // 2):
        # shifting the grid by k beats: beat i gets the bar position of beat i+k
        flags = np.roll(downbeat_flags, -k)[beat_idx]
        scores.append((float(change[flags].mean()) if flags.any() else -1, -abs(k), k))
    k = max(scores)[2]
    best_d = best_d - k * period
    _offset_cache[song_id] = float(best_d)
    return float(best_d)


@contextmanager
def timer(store, key):
    t0 = time.perf_counter()
    yield
    store[key] = time.perf_counter() - t0


def save_result(name, obj, merge=False):
    """Write results/<name>.json; merge=True keeps keys from earlier runs."""
    path = os.path.join(RESULTS, f"{name}.json")
    if merge and os.path.exists(path):
        old = json.load(open(path))
        old.update(obj)
        obj = old
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=float)
    print("saved", path)


def usdr(ref, est):
    """Utterance SDR used by the Music Demixing challenges (higher = better)."""
    n = min(len(ref), len(est))
    ref, est = ref[:n], est[:n]
    num = np.sum(ref ** 2) + 1e-8
    den = np.sum((ref - est) ** 2) + 1e-8
    return float(10 * np.log10(num / den))
