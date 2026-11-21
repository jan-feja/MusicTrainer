"""Record-and-compare: can we score a user's take automatically?

We fake a user playing the bass line, with known mistakes:
  - 137 ms recording latency (sound card / browser)
  - random timing wobble (std 15 ms) and bars 20-23 played 40 ms early (rushing)
  - 6 % wrong notes (1-2 semitones off), 5 % missed notes
  - different bass sound (picked instead of fingered)
Two recording conditions:
  di     instrument plugged in / headphones (clean)
  room   microphone in the room: the song from the speakers bleeds in, plus noise
Pipeline: estimate latency -> transcribe the take (Basic Pitch) -> match notes
to the reference part -> report wrong / missed notes and timing per bar.
Then we check the report against the mistakes we injected.
"""
import os
import random
import subprocess
import warnings

import librosa
import mir_eval
import numpy as np
import pretty_midi
import soundfile as sf

from common import DATA, save_result, synth_dir
from test_transcription import basic_pitch_notes

warnings.filterwarnings("ignore")
SR = 44100
LATENCY = 0.137
BAR = 2.4  # seconds per bar at 100 BPM
OUT = os.path.join(DATA, "scoring")


def make_take(seed=3):
    rnd = random.Random(seed)
    ref = pretty_midi.PrettyMIDI(os.path.join(synth_dir("steady"), "bass.mid")).instruments[0].notes
    take = pretty_midi.Instrument(program=34, name="take")
    truth = {"wrong": set(), "missed": set(), "dev": {}}
    for i, n in enumerate(ref):
        if rnd.random() < 0.05:
            truth["missed"].add(i)
            continue
        dev = rnd.gauss(0, 0.015)
        bar = int((n.start - 0.5) // BAR)
        if 20 <= bar <= 23:
            dev -= 0.040
        pitch = n.pitch
        if rnd.random() < 0.06:
            pitch += rnd.choice([-2, -1, 1, 2])
            truth["wrong"].add(i)
        truth["dev"][i] = dev
        s = n.start + dev + LATENCY
        take.notes.append(pretty_midi.Note(velocity=max(40, n.velocity + rnd.randint(-15, 10)), pitch=pitch,
                                           start=s, end=s + (n.end - n.start) * rnd.uniform(0.7, 1.0)))
    return ref, take, truth


def render(inst, path):
    pm = pretty_midi.PrettyMIDI(initial_tempo=100)
    pm.instruments.append(inst)
    mid = path.replace(".wav", ".mid")
    pm.write(mid)
    subprocess.run([os.environ["FLUIDSYNTH"], "-ni", "-q", "-g", "0.6", "-r", str(SR), "-F", path,
                    os.environ["SOUNDFONT"], mid], check=True, capture_output=True)
    y, _ = sf.read(path, always_2d=True)
    return y.mean(1)


def estimate_latency(take, reference):
    """Cross-correlate onset envelopes; returns how late the take is (s)."""
    hop = 441  # 10 ms
    a = librosa.onset.onset_strength(y=take.astype(np.float32), sr=SR, hop_length=hop)
    b = librosa.onset.onset_strength(y=reference.astype(np.float32), sr=SR, hop_length=hop)
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    lags = np.arange(-50, 51)
    xc = [np.dot(a[max(0, l):n + min(0, l)], b[max(0, -l):n - max(0, l)]) for l in lags]
    return lags[int(np.argmax(xc))] * hop / SR


def analyse(take_wav, ref_notes, ref_audio, latency=None):
    take_audio, _ = sf.read(take_wav)
    if take_audio.ndim == 2:
        take_audio = take_audio.mean(1)
    lat = estimate_latency(take_audio, ref_audio) if latency is None else latency
    ints, pitches = basic_pitch_notes(take_wav, "bass")
    ints = ints - lat
    ri = np.array([[n.start, n.end] for n in ref_notes])
    rp = np.array([n.pitch for n in ref_notes])
    matches = mir_eval.transcription.match_notes(ri, mir_eval.util.midi_to_hz(rp), ints, mir_eval.util.midi_to_hz(pitches),
                                                 onset_tolerance=0.1, pitch_tolerance=50.0, offset_ratio=None)
    matched_ref = {r: e for r, e in matches}
    report = {"latency_estimate": lat, "wrong": set(), "missed": set(), "dev": {}}
    for i in range(len(ref_notes)):
        if i in matched_ref:
            report["dev"][i] = ints[matched_ref[i], 0] - ri[i, 0]
            continue
        near = np.where(np.abs(ints[:, 0] - ri[i, 0]) < 0.1)[0]
        (report["wrong"] if len(near) else report["missed"]).add(i)
    return report


def prf(found, truth):
    tp = len(found & truth)
    p = tp / len(found) if found else 1.0
    r = tp / len(truth) if truth else 1.0
    return round(p, 2), round(r, 2)


def main():
    os.makedirs(OUT, exist_ok=True)
    ref_notes, take_inst, truth = make_take()
    clean = render(take_inst, os.path.join(OUT, "take_di.wav"))
    ref_audio, _ = sf.read(os.path.join(synth_dir("steady"), "stems", "bass.wav"))
    ref_audio = ref_audio.mean(1)
    # room take: backing track (song without bass) bleeds in at -12 dB, plus noise
    backing = sum(sf.read(os.path.join(synth_dir("steady"), "stems", f"{s}.wav"))[0].mean(1)
                  for s in ("drums", "guitar", "piano", "vocals"))
    # the speakers' sound reaches the mic together with the player's notes, so
    # it carries the same recording latency
    backing = np.concatenate([np.zeros(int(LATENCY * SR)), backing])
    n = min(len(clean), len(backing))
    room = clean[:n] + 0.25 * backing[:n] + np.random.default_rng(0).normal(0, 0.003, n)
    room /= np.abs(room).max() / 0.9
    sf.write(os.path.join(OUT, "take_room.wav"), room, SR)
    # room take cleaned up by running Demucs on it and keeping only the bass
    from common import DEVICE
    from test_separation import demucs_separate
    stems = demucs_separate("htdemucs", np.stack([room, room], 1), SR, DEVICE)
    sf.write(os.path.join(OUT, "take_room_separated.wav"), stems["bass"].mean(1), SR)

    res = {}
    # "+cal": latency measured beforehand with a click/loopback calibration
    # (simulated as the true value plus a 5 ms measuring error)
    for cond in ("di", "room", "room_separated", "room+cal", "room_separated+cal"):
        lat = LATENCY + 0.005 if cond.endswith("+cal") else None
        rep = analyse(os.path.join(OUT, f"take_{cond.replace('+cal', '')}.wav"), ref_notes, ref_audio, lat)
        common_ids = [i for i in rep["dev"] if i in truth["dev"]]
        est_dev = np.array([rep["dev"][i] for i in common_ids])
        true_dev = np.array([truth["dev"][i] for i in common_ids])
        bars = {}
        for i in common_ids:
            bars.setdefault(int((ref_notes[i].start - 0.5) // BAR), []).append(rep["dev"][i])
        flagged = sorted(b for b, d in bars.items() if np.mean(d) < -0.025)
        r = {
            "latency_true_ms": LATENCY * 1000, "latency_est_ms": round(rep["latency_estimate"] * 1000, 1),
            "wrong_notes_precision_recall": prf(rep["wrong"], truth["wrong"]),
            "missed_notes_precision_recall": prf(rep["missed"], truth["missed"]),
            "timing_corr_with_truth": round(float(np.corrcoef(est_dev, true_dev)[0, 1]), 3),
            "timing_mean_abs_error_ms": round(float(np.mean(np.abs(est_dev - true_dev - np.mean(est_dev - true_dev)))) * 1000, 1),
            "bars_flagged_rushing": flagged, "bars_truly_rushing": [20, 21, 22, 23],
            "notes_total": len(ref_notes), "wrong_true": len(truth["wrong"]), "missed_true": len(truth["missed"]),
            "wrong_found": len(rep["wrong"]), "missed_found": len(rep["missed"]),
        }
        res[cond] = r
        print(cond, r)
    save_result("scoring", res)


if __name__ == "__main__":
    main()
