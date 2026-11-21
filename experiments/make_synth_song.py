"""Render a synthetic band song with exact ground truth.

Creates a 52-bar song in E minor (drums, bass, guitar, piano, "voice" lead),
renders every instrument separately with FluidSynth (= ground-truth stems)
and writes the answers every test needs: beats, downbeats, BPM, key,
chords, sections and the MIDI notes of each instrument.

Variants:
  steady   constant 100 BPM
  live     tempo drifts between ~92 and ~108 BPM
  detune   steady, but every pitched instrument is 35 cents flat
  eb       steady, everything a semitone down (Eb tuning)

Usage: python make_synth_song.py <out_dir> [variant ...]
Needs env vars FLUIDSYNTH (path to fluidsynth.exe) and SOUNDFONT (.sf2).
"""
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
import pretty_midi
import soundfile as sf

SR = 44100
BPM = 100.0
BEATS_PER_BAR = 4

# (label, chords per bar)
SECTIONS = [
    ("intro", ["Em", "C", "G", "D"]),
    ("verse", ["Em", "C", "G", "D"] * 2),
    ("chorus", ["C", "G", "D", "Em"] * 2),
    ("verse", ["Em", "C", "G", "D"] * 2),
    ("chorus", ["C", "G", "D", "Em"] * 2),
    ("bridge", ["Am", "C", "D", "D"]),
    ("chorus", ["C", "G", "D", "Em"] * 2),
    ("outro", ["Em", "C", "G", "Em"]),
]

CHORD_PITCHES = {  # root midi note (octave 2) and triad intervals
    "Em": (40, [0, 7, 12, 15, 19]),
    "C": (36, [0, 7, 12, 16, 19]),
    "G": (43, [0, 7, 12, 16, 19]),
    "D": (38, [0, 7, 12, 16, 19]),
    "Am": (45, [0, 7, 12, 15, 19]),
}
E_MINOR_PENTA = [64, 67, 69, 71, 74, 76, 79]


def make_warp(variant):
    """Return beat -> seconds function."""
    if variant == "live":
        # tempo(b) = BPM * (1 + 0.08 sin(2 pi b / 48)); integrate numerically
        n = 52 * BEATS_PER_BAR + 8
        step = 0.01
        bs = np.arange(0, n + step, step)
        bpm = BPM * (1 + 0.08 * np.sin(2 * np.pi * bs / 48.0))
        t = np.concatenate([[0], np.cumsum(60.0 / bpm[:-1] * step)])
        return lambda b: float(np.interp(b, bs, t)) + 0.5
    return lambda b: 0.5 + b * 60.0 / BPM  # 0.5 s of silence at the start


def build(variant, seed=1):
    rnd = random.Random(seed)
    warp = make_warp(variant)
    transpose = -1 if variant == "eb" else 0
    detune_cents = -35 if variant == "detune" else 0

    drums = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    bass = pretty_midi.Instrument(program=33, name="bass")
    guitar = pretty_midi.Instrument(program=29, name="guitar")
    piano = pretty_midi.Instrument(program=0, name="piano")
    lead = pretty_midi.Instrument(program=53, name="vocals")  # "Voice Oohs"

    def note(inst, pitch, b0, b1, vel):
        inst.notes.append(pretty_midi.Note(
            velocity=max(1, min(127, vel)), pitch=pitch + (0 if inst.is_drum else transpose),
            start=warp(b0), end=warp(b1)))

    chords_gt, sections_gt = [], []
    bar = 0
    for s_idx, (label, chords) in enumerate(SECTIONS):
        s_start = bar
        for i, ch in enumerate(chords):
            b = bar * BEATS_PER_BAR
            root, ivs = CHORD_PITCHES[ch]
            last_bar = i == len(chords) - 1
            chorus = label == "chorus"
            # drums
            if i == 0:
                note(drums, 49, b, b + 1, 110)  # crash
            for k in range(8):
                if not (last_bar and k >= 6):
                    note(drums, 42, b + k / 2, b + k / 2 + 0.25, 70 + rnd.randint(-10, 10) + (15 if k % 2 == 0 else 0))
            note(drums, 36, b, b + 0.5, 110)
            note(drums, 36, b + 2, b + 2.5, 105)
            if chorus:
                note(drums, 36, b + 2.5, b + 3, 95)
            note(drums, 38, b + 1, b + 1.5, 105)
            if last_bar and label != "outro":
                for k in range(4):  # fill
                    note(drums, 38 if k % 2 == 0 else 45, b + 3 + k / 4, b + 3 + k / 4 + 0.2, 90 + 5 * k)
            else:
                note(drums, 38, b + 3, b + 3.5, 105)
            # bass: 8th-note roots (not in intro)
            if label != "intro":
                for k in range(8):
                    p = root if k != 7 else root + 7
                    note(bass, p, b + k / 2, b + k / 2 + 0.45, 95 + rnd.randint(-8, 8))
            # guitar: strummed 8ths (down-up), not in bridge
            if label != "bridge":
                for k in range(8):
                    if label == "verse" and k in (3, 5):
                        continue
                    strings = ivs if k % 2 == 0 else ivs[::-1][:3]
                    for j, iv in enumerate(strings):
                        off = j * 0.012
                        note(guitar, root + 12 + iv, b + k / 2 + off, b + k / 2 + 0.48, 80 + (10 if k % 2 == 0 else -5))
            # piano: whole-bar triads in chorus, bridge, outro
            if label in ("chorus", "bridge", "outro"):
                for iv in ivs[2:]:
                    note(piano, root + 24 + iv - 12, b, b + 4, 75)
            # lead melody in verse / chorus
            if label in ("verse", "chorus"):
                base = 2 if chorus else 0
                for k in range(4):
                    if rnd.random() < 0.8:
                        p = E_MINOR_PENTA[min(len(E_MINOR_PENTA) - 1, base + rnd.randint(0, 4))]
                        note(lead, p, b + k, b + k + 0.9, 90)
            chords_gt.append([warp(b), warp(b + 4), ch])
            bar += 1
        sections_gt.append([warp(s_start * 4), warp(bar * 4), label])

    insts = [drums, bass, guitar, piano, lead]
    if detune_cents:
        bend = int(detune_cents / 200.0 * 8192)
        for inst in insts:
            if not inst.is_drum:
                inst.pitch_bends.append(pretty_midi.PitchBend(bend, 0.0))

    n_beats = bar * BEATS_PER_BAR
    beats = [warp(k) for k in range(n_beats + 1)]
    downbeats = beats[::BEATS_PER_BAR]
    names = {0: "E", -1: "D#"}
    gt = {
        "variant": variant,
        "bpm": BPM,
        "tempo_varies": variant == "live",
        "key": f"{names[transpose]} minor",
        "tuning_cents": detune_cents,
        "beats": beats,
        "downbeats": downbeats,
        "chords": chords_gt if not transpose else [[a, b, shift_chord(c, transpose)] for a, b, c in chords_gt],
        "sections": sections_gt,
    }
    return insts, gt


def shift_chord(ch, semis):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    minor = ch.endswith("m")
    root = ch[:-1] if minor else ch
    r = (names.index(root) + semis) % 12
    return names[r] + ("m" if minor else "")


def render(insts, out_dir):
    fs_exe, sf2 = os.environ["FLUIDSYNTH"], os.environ["SOUNDFONT"]
    os.makedirs(os.path.join(out_dir, "stems"), exist_ok=True)
    stems = {}
    for inst in insts:
        pm = pretty_midi.PrettyMIDI(initial_tempo=BPM)
        pm.instruments.append(inst)
        mid = os.path.join(out_dir, f"{inst.name}.mid")
        pm.write(mid)
        wav = os.path.join(out_dir, "stems", f"{inst.name}.wav")
        subprocess.run([fs_exe, "-ni", "-q", "-g", "0.6", "-r", str(SR), "-F", wav, sf2, mid],
                       check=True, capture_output=True)
        y, _ = sf.read(wav, always_2d=True)
        stems[inst.name] = y
    n = max(len(y) for y in stems.values())
    stems = {k: np.pad(v, ((0, n - len(v)), (0, 0))) for k, v in stems.items()}
    mix = sum(stems.values())
    gain = 0.89 / np.abs(mix).max()
    for k, v in stems.items():
        sf.write(os.path.join(out_dir, "stems", f"{k}.wav"), v * gain, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "mix.wav"), mix * gain, SR, subtype="FLOAT")
    full = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    full.instruments.extend(insts)
    full.write(os.path.join(out_dir, "song.mid"))


if __name__ == "__main__":
    out_root = sys.argv[1]
    variants = sys.argv[2:] or ["steady", "live", "detune", "eb"]
    for v in variants:
        d = os.path.join(out_root, f"synth_{v}")
        insts, gt = build(v)
        render(insts, d)
        with open(os.path.join(d, "ground_truth.json"), "w") as f:
            json.dump(gt, f, indent=1)
        print(f"{v}: {d}  ({gt['beats'][-1]:.1f} s, key {gt['key']})")
