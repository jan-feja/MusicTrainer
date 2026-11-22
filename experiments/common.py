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


MEL = {"sr": 22050, "n_mels": 80, "n_fft": 2048, "hop_length": 1024}  # Harmonix_melspecs.tgz info.json
WARP_WINDOW = 10.0  # seconds: the DTW path is smoothed by straight-line fits over windows this long
WARP_SLOPE = 0.02  # a beat is kept where the fit runs at the same speed (+-2 %) ...
WARP_RESIDUAL = 0.05  # ... and follows the path closely (seconds RMS): no cut inside the window
WARP_MIN_SHARE = 0.5  # the longest stretch of kept beats must cover this share of the song
WARP_FINE = 0.08  # seconds: last, the beats are shifted (at most this far) onto the strongest onsets


def harmonix_warped(song_id, wav):
    """Annotated beats and bar positions moved onto the YouTube audio, or None if too little matches.

    A constant shift (harmonix_offset) is not enough for many songs: YouTube versions can have a
    longer intro, a cut verse, an inserted interlude or another master. The Harmonix authors align
    YouTube audio to the audio they annotated with DTW on mel spectrograms and publish those
    spectrograms (Harmonix_melspecs.tgz, unpacked to MT_DATA/harmonix_melspecs/melspecs/). Here:
      1. DTW between the published and the YouTube mel spectrogram (log, cosine distance);
      2. every annotated beat is mapped by a straight-line fit to the path over +-5 s (sub-frame
         precision); it is kept where that line runs at the same speed and fits the path, i.e.
         no cut or insertion nearby;
      3. the longest unbroken stretch of kept beats is the song's answer (at least half the song);
      4. as in harmonix_offset, a last small shift puts the beats on the strongest onsets (the
         published spectrograms lag the annotations by about an MP3 decoder delay, ~25 ms).
    Returns (beat times, beat positions in the bar) in YouTube time; cached in harmonix/aligned/.
    """
    cache = os.path.join(DATA, "harmonix", "aligned", f"{song_id}.json")
    if os.path.exists(cache):
        data = json.load(open(cache))
        return None if data is None else (np.array(data["beats"]), np.array(data["positions"]))
    import librosa

    reference = np.load(os.path.join(DATA, "harmonix_melspecs", "melspecs", f"{song_id}-mel.npy"))
    y, _ = librosa.load(wav, sr=MEL["sr"], mono=True)
    ours = librosa.feature.melspectrogram(y=y, **MEL)
    ref_log, our_log = np.log1p(reference) + 1e-3, np.log1p(ours) + 1e-3  # no all-zero frames (cosine)
    _, path = librosa.sequence.dtw(X=ref_log, Y=our_log, metric="cosine")
    path = path[::-1].astype(float) * MEL["hop_length"] / MEL["sr"]  # (reference time, YouTube time)
    rows = np.loadtxt(os.path.join(DATA, "harmonix", "ann", f"{song_id}.beats_and_downbeats.txt"))
    beats, positions = rows[:, 0], rows[:, 1].astype(int)
    duration = len(y) / MEL["sr"]
    mapped, kept = np.empty(len(beats)), np.zeros(len(beats), dtype=bool)
    for i, t in enumerate(beats):
        near = np.abs(path[:, 0] - t) <= WARP_WINDOW / 2
        slope, intercept = np.polyfit(path[near, 0], path[near, 1], 1)
        residual = np.sqrt(np.mean((slope * path[near, 0] + intercept - path[near, 1]) ** 2))
        mapped[i] = slope * t + intercept
        kept[i] = abs(slope - 1) < WARP_SLOPE and residual < WARP_RESIDUAL and 0.05 < mapped[i] < duration - 0.05
    # longest unbroken run of kept beats
    best, run_start = (0, 0), None
    for i, k in enumerate(np.append(kept, False)):
        if k and run_start is None:
            run_start = i
        elif not k and run_start is not None:
            best = max(best, (i - run_start, run_start))
            run_start = None
    length, first = best
    result = None
    if length >= WARP_MIN_SHARE * len(beats):
        run = slice(first, first + length)
        hop = 220  # 10 ms
        envelope = librosa.onset.onset_strength(y=y, sr=MEL["sr"], hop_length=hop)
        times = mapped[run]

        def onset_score(shift: float) -> float:
            frames = np.round((times + shift) * MEL["sr"] / hop).astype(int)
            frames = frames[(frames >= 1) & (frames < len(envelope) - 1)]
            return float(np.mean(np.maximum(np.maximum(envelope[frames - 1], envelope[frames]), envelope[frames + 1])))

        shift = max(np.arange(-WARP_FINE, WARP_FINE + 1e-9, 0.005), key=onset_score)
        result = {"beats": (times + shift).tolist(), "positions": positions[run].tolist(), "shift": float(shift)}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(result, open(cache, "w"))
    return None if result is None else (np.array(result["beats"]), np.array(result["positions"]))


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
