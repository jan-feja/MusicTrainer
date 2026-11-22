"""Write beat-tracking test songs as scores (multi-track MIDI files).

Each song is a list of sections: number of bars, time signature, tempo (steady,
ramp, rubato, drift) and a groove for every part. The result is an ordinary
MIDI file with a real tempo map and time signatures, so every beat and bar
start follows from the score. score_to_audio.py renders it to audio and writes
the ground truth, the same way it handles Guitar Pro files and other MIDI files.

The songs target what beat trackers get wrong: half-time and double-time
feels, sustained leads, odd and compound meters, single odd bars, tempo jumps,
rubato, ritardando, no drums, swing, off-beat accents, stops and a drifting
live tempo. A sidecar <name>.json holds the category and render options.

Usage: python make_score_songs.py <out_dir> [variants]
  variants (default 1): also write <name>_v1, _v2, ... with the tempo scaled
  (x0.87, x1.15, x0.93, x1.07) and other random choices (fills, melodies, mix)
"""

import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import mido

TPQ = 480  # MIDI ticks per quarter note

# General MIDI drum notes
KICK, SIDESTICK, SNARE, HAT, PEDAL_HAT, OPEN_HAT = 36, 37, 38, 42, 44, 46
CRASH, RIDE, CHINA, FLOOR_TOM, LOW_TOM, MID_TOM, HIGH_TOM = 49, 51, 52, 41, 45, 47, 50

PITCH_CLASS = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
CHANNELS = {"bass": 0, "guitar": 1, "keys": 2, "lead": 3, "drums": 9}


@dataclass
class Section:
    name: str
    bars: int
    meter: tuple[int, int] = (4, 4)
    tempo: float | tuple[float, float] = 120.0  # beats per minute; a pair is a linear ramp
    rubato: float = 0.0  # random tempo change per beat (0.1 = about +-10 %)
    drums: str = "rock"
    bass: str = "eighths"
    guitar: str = "strum"
    keys: str = "none"
    lead: str = "none"
    chords: tuple[str, ...] = ("Am", "F", "C", "G")  # one per bar, repeated
    fill: bool = True  # drum fill in the last bar
    fermata: bool = False  # the last beat lasts four times as long


@dataclass
class Song:
    name: str
    category: str
    sections: list[Section]
    programs: dict[str, int] = field(default_factory=lambda: {"bass": 33, "guitar": 27, "keys": 0, "lead": 29})
    seed: int = 0
    drift: float = 0.0  # slow tempo drift, fraction of the tempo (0.04 = +-4 %)
    drift_period_bars: float = 16.0
    humanize: float = 1.0  # timing-jitter scale used by score_to_audio.py
    effects: str = "band"  # mix preset used by score_to_audio.py


def beat_layout(meter: tuple[int, int]) -> tuple[int, float, int]:
    """Beats per bar, beat length in quarter notes, subdivisions per beat."""
    num, den = meter
    if den == 8 and num % 3 == 0 and num > 3:  # compound: 6/8, 9/8, 12/8 count dotted quarters
        return num // 3, 1.5, 3
    return num, 4 / den, 2


def accent_groups(beats: int) -> list[int]:
    return {5: [3, 2], 7: [4, 3], 6: [3, 3]}.get(beats, [beats])


def chord_tones(name: str) -> tuple[int, list[int]]:
    minor = name.endswith("m")
    return PITCH_CLASS[name[:-1] if minor else name], [0, 3 if minor else 4, 7]


class Score:
    """Notes of all parts in quarter-note time, plus the tempo map."""

    def __init__(self, seed: int) -> None:
        self.rnd = random.Random(seed)
        self.notes: dict[str, list[tuple[float, float, int, int]]] = {}
        self.tempos: list[tuple[float, float]] = []  # (quarter position, quarter-note BPM)
        self.meters: list[tuple[float, tuple[int, int]]] = []
        self.markers: list[tuple[float, str]] = []

    def add(self, part: str, start: float, length: float, pitch: int, velocity: int) -> None:
        velocity = max(1, min(127, velocity + self.rnd.randint(-6, 6)))
        self.notes.setdefault(part, []).append((start, max(length, 0.05), pitch, velocity))


class Bar:
    """Helpers for writing one bar: positions are in beats from the bar start."""

    def __init__(self, score: Score, start: float, meter: tuple[int, int], chord: str, next_chord: str) -> None:
        self.score, self.start, self.meter = score, start, meter
        self.beats, self.beat_len, self.subs = beat_layout(meter)
        self.root, self.intervals = chord_tones(chord)
        self.next_root = chord_tones(next_chord)[0]
        self.rnd = score.rnd

    def note(self, part: str, beat: float, beats_long: float, pitch: int, velocity: int) -> None:
        if beat < self.beats - 1e-9:
            self.score.add(part, self.start + beat * self.beat_len, beats_long * self.beat_len, pitch, velocity)

    def sub_positions(self, per_beat: int | None = None) -> list[float]:
        per_beat = per_beat or self.subs
        return [i / per_beat for i in range(self.beats * per_beat)]

    def bass_pitch(self, interval: int = 0) -> int:
        return 28 + (self.root - 4) % 12 + interval  # E1 .. D#2

    def chord_pitches(self, base: int = 52) -> list[int]:
        root = base + (self.root - 4) % 12
        return [root + i for i in self.intervals] + [root + 12]


# --- parts -----------------------------------------------------------------------------------


def drums(bar: Bar, style: str, first: bool, last: bool, fill: bool) -> None:
    n, d = bar.beats, "drums"
    hit = lambda beat, pitch, vel: bar.note(d, beat, 0.1, pitch, vel)  # noqa: E731
    fill_from = n - 1 if (last and fill and style not in ("none", "stops")) else n
    if style == "none":
        return
    if style in ("rock", "halftime", "double", "waltz", "brushes", "onedrop"):
        per_beat = 4 if style == "double" else bar.subs
        for pos in bar.sub_positions(per_beat):
            if pos < fill_from:
                if style == "brushes":
                    if pos % 1 == 0 and pos % 2 == 1:
                        hit(pos, PEDAL_HAT, 55)
                else:
                    hit(pos, HAT, 80 if pos % 1 == 0 else 55)
        if style == "rock":
            start = 0
            for size in accent_groups(n):
                if size == 2:
                    plan = [(0, KICK), (1, SNARE)]
                elif size == 3:
                    plan = [(0, KICK), (2, SNARE)] if n != 3 else [(0, KICK), (1, SNARE), (2, SNARE)]
                else:
                    plan = [(0, KICK), (1, SNARE), (2, KICK), (3, SNARE)]
                    if bar.rnd.random() < 0.5:
                        plan.append((2.5, KICK))
                for offset, pitch in plan:
                    if start + offset < fill_from:
                        hit(start + offset, pitch, 105 if pitch == KICK else 100)
                start += size
        elif style == "halftime":
            hit(0, KICK, 110)
            if bar.rnd.random() < 0.6:
                hit(1.5, KICK, 90)
            if n // 2 < fill_from:
                hit(n // 2, SNARE, 110)
        elif style == "double":
            for b in range(n):
                if b < fill_from:
                    hit(b, KICK, 105)
                    hit(b + 0.5, SNARE, 100)
        elif style == "waltz":
            hit(0, KICK, 105)
            for b in range(1, n):
                if b < fill_from:
                    hit(b, SNARE, 60)
        elif style == "brushes":
            for b in range(1, n, 2):
                if b < fill_from:
                    hit(b, SIDESTICK, 70)
            hit(0, KICK, 75)
        elif style == "onedrop":  # kick and rim only on beat 3 (of 4)
            if n // 2 < fill_from:
                hit(n // 2, KICK, 110)
                hit(n // 2, SIDESTICK, 100)
    elif style == "shuffle":
        for b in range(n):
            if b < fill_from:
                hit(b, RIDE, 85)
                hit(b + 2 / 3, RIDE, 60)
                hit(b, KICK if b % 2 == 0 else SNARE, 100)
    elif style == "funk":
        for pos in bar.sub_positions(4):
            if pos < fill_from:
                hit(pos, HAT, 75 if pos % 0.5 == 0 else 45)
        for pos, pitch, vel in ((0, KICK, 110), (0.75, KICK, 90), (2.5, KICK, 100), (1, SNARE, 105), (3, SNARE, 105),
                                (1.75, SNARE, 28), (2.25, SNARE, 25), (3.75, SNARE, 30)):
            if pos < min(n, fill_from) and (pitch != KICK or pos == 0 or bar.rnd.random() < 0.8):
                hit(pos, pitch, vel)
    elif style == "swing":
        for b in range(n):
            if b < fill_from:
                hit(b, RIDE, 80)
                hit(b, KICK, 35)
                if b % 2 == 1:
                    hit(b, PEDAL_HAT, 70)
                    hit(b + 2 / 3, RIDE, 60)
                if bar.rnd.random() < 0.3:
                    hit(b + 2 / 3, SNARE, 50)
    elif style == "metal":
        for pos in bar.sub_positions(4):
            if pos < fill_from:
                hit(pos, KICK, 95)
        for b in range(n):
            if b < fill_from:
                hit(b, CRASH if b % 2 == 0 else CHINA, 90)
                if b % 2 == 1:
                    hit(b, SNARE, 115)
    elif style == "metal_half":
        for pos in (0, 0.75, 1.5, 2.75, 3.25):
            if pos < min(n, fill_from):
                hit(pos, KICK, 110)
        for b in range(n):
            if b < fill_from:
                hit(b, CHINA, 95)
        if n // 2 < fill_from:
            hit(n // 2, SNARE, 120)
    elif style == "stops":
        hit(0, KICK, 115)
        hit(0, CRASH, 110)
    else:
        raise ValueError(style)
    if first and style not in ("stops", "brushes"):
        hit(0, CRASH, 105)
    if fill_from < n:
        for i in range(4):
            hit(fill_from + i / 4, (SNARE, HIGH_TOM, MID_TOM, FLOOR_TOM)[i], 85 + 8 * i)


def bass(bar: Bar, style: str) -> None:
    n, p = bar.beats, bar.bass_pitch
    if style == "none":
        return
    if style == "eighths":
        positions = bar.sub_positions()
        for i, pos in enumerate(positions):
            bar.note("bass", pos, 0.9 / bar.subs, p(7 if i == len(positions) - 1 else 0), 95)
    elif style == "quarters":
        for b in range(n):
            bar.note("bass", b, 0.9, p((0, 7, 12, 7)[b % 4]), 95)
    elif style == "half":
        bar.note("bass", 0, n / 2 - 0.1, p(), 95)
        bar.note("bass", n // 2, n - n // 2 - 0.1, p(7), 90)
    elif style == "whole":
        bar.note("bass", 0, n - 0.1, p(), 90)
    elif style == "walking":
        approach = 28 + (bar.next_root - 4) % 12 + bar.rnd.choice((-1, 1))
        tones = [p(), p(bar.intervals[1]), p(7), approach]
        for b in range(n):
            bar.note("bass", b, 0.9, tones[min(b, 3)] if b < 3 or b == n - 1 else p(12), 90)
    elif style == "funk":
        for pos, interval in ((0, 0), (0.75, 12), (1.5, 0), (2, 7), (2.75, 12), (3.25, 10), (3.5, 0)):
            if pos < n:
                bar.note("bass", pos, 0.2, p(interval), 100 if pos % 1 == 0 else 80)
    elif style == "reggae":
        for pos, interval in ((0.5, 0), (1, 7), (2.5, 12), (3, 10)):
            if pos < n:
                bar.note("bass", pos, 0.45, p(interval), 100)
    else:
        raise ValueError(style)


def guitar(bar: Bar, style: str) -> None:
    n, chord, g = bar.beats, bar.chord_pitches(), "guitar"
    if style == "none":
        return
    if style == "strum":
        for pos in bar.sub_positions():
            down = pos % 1 == 0
            if not down and bar.rnd.random() < 0.3:
                continue
            strings = chord if down else chord[::-1][:3]
            for i, pitch in enumerate(strings):
                bar.note(g, pos + i * 0.015, 0.95 / bar.subs, pitch, 85 if down else 62)
    elif style in ("arpeggio", "arp16"):
        per_beat = 4 if style == "arp16" else bar.subs
        order = [chord[0], chord[2], chord[3], chord[1] + 12, chord[3], chord[2]]
        for i, pos in enumerate(bar.sub_positions(per_beat)):
            bar.note(g, pos, 2.0 / per_beat, order[i % len(order)], 72 if pos % 1 == 0 else 60)
    elif style == "power":
        root = chord[0] - 12
        for pos in bar.sub_positions():
            for pitch in (root, root + 7, root + 12):
                bar.note(g, pos, 0.4 / bar.subs, pitch, 95 if pos % 1 == 0 else 80)
    elif style == "offbeat":  # reggae / ska skank on the "and"
        for b in range(n):
            for pitch in chord[1:]:
                bar.note(g, b + 0.5, 0.2, pitch + 12, 85)
    elif style == "shuffle":
        for b in range(n):
            for offset, vel in ((0, 85), (2 / 3, 65)):
                for pitch in (chord[0] - 12, chord[0] - 5):
                    bar.note(g, b + offset, 0.3, pitch, vel)
    elif style == "scratch16":
        for pos in bar.sub_positions(4):
            accent = pos % 1 in (0.25, 0.75) and bar.rnd.random() < 0.5
            for pitch in chord[1:]:
                bar.note(g, pos, 0.08, pitch + 12, 90 if accent else 40)
    elif style == "fingerpick":  # alternating bass on the beat, treble on the off-beats
        for b in range(n):
            bar.note(g, b, 0.9, chord[0] - (0 if b % 2 == 0 else 5), 80)
            for k in range(1, bar.subs):
                bar.note(g, b + k / bar.subs, 0.6, chord[1 + (b + k) % 3] + 12, 62)
    elif style == "sustain":
        for i, pitch in enumerate(chord):
            bar.note(g, i * 0.02, n - 0.1, pitch, 70)
    else:
        raise ValueError(style)


def keys(bar: Bar, style: str) -> None:
    n, chord, k = bar.beats, bar.chord_pitches(60), "keys"
    if style == "none":
        return
    if style == "pad":
        for pitch in chord[:3]:
            bar.note(k, 0, n, pitch, 60)
    elif style == "piano":
        bar.note(k, 0, n / 2, chord[0] - 24, 80)
        for b in range(n):
            for pitch in chord:
                bar.note(k, b, 0.9, pitch, 72 if b == 0 else 60)
    elif style == "waltz":
        bar.note(k, 0, 0.9, chord[0] - 24, 90)
        for b in range(1, n):
            for pitch in chord[:3]:
                bar.note(k, b, 0.8, pitch, 65)
    elif style == "comp":  # jazz comping: short chords off the beat
        for b in range(n):
            if bar.rnd.random() < 0.45:
                for pitch in chord[:3]:
                    bar.note(k, b + bar.rnd.choice((0, 2 / 3)), 0.3, pitch, 70)
    elif style == "rubato_piano":
        order = [chord[0] - 24, chord[0] - 12, chord[2] - 12, chord[0], chord[1], chord[2], chord[3], chord[2]]
        for i, pos in enumerate(bar.sub_positions()):
            bar.note(k, pos, n - pos, order[i % len(order)], 70 if i == 0 else 55)
    else:
        raise ValueError(style)


def lead(bar: Bar, style: str, scale: list[int]) -> None:
    n, ld, rnd = bar.beats, "lead", bar.rnd
    if style == "none":
        return
    if style == "melody":
        for pos in bar.sub_positions():
            if rnd.random() < (0.55 if pos % 1 == 0 else 0.3):
                bar.note(ld, pos, 0.9 / bar.subs * rnd.choice((1, 2)), rnd.choice(scale), 88)
    elif style == "fast":
        positions = bar.sub_positions(4)
        start = rnd.choice((0, n / 2))
        idx = rnd.randrange(len(scale) - 4)
        for pos in positions:
            if start <= pos < start + n / 2:
                idx = max(0, min(len(scale) - 1, idx + rnd.choice((-1, 1, 1))))
                bar.note(ld, pos, 0.24, scale[idx], 92)
        bar.note(ld, (start + n / 2) % n, n / 2 - 0.2, rnd.choice(scale), 95)
    elif style == "long":  # sustained notes that start off the beat
        pos = rnd.choice((0.5, 1.25, 0.75)) if n > 1 else 0.5
        bar.note(ld, pos, n - pos + rnd.choice((0, 0.5)), rnd.choice(scale), 90)
    else:
        raise ValueError(style)


# --- song assembly ----------------------------------------------------------------------------


def build(song: Song) -> Score:
    score = Score(song.seed)
    key_root = chord_tones(song.sections[0].chords[0])[0]
    scale = sorted({60 + (key_root + i) % 12 + 12 * octave for i in (0, 3, 5, 7, 10) for octave in (0, 1)})
    position, bar_index, last_meter = 0.0, 0, None
    for s_idx, section in enumerate(song.sections):
        score.markers.append((position, section.name))
        beats, beat_len, _ = beat_layout(section.meter)
        if section.meter != last_meter:
            score.meters.append((position, section.meter))
            last_meter = section.meter
        total_beats = section.bars * beats
        noise = 0.0
        for bar in range(section.bars):
            chord = section.chords[bar % len(section.chords)]
            next_chord = section.chords[(bar + 1) % len(section.chords)]
            b = Bar(score, position, section.meter, chord, next_chord)
            first, last = bar == 0, bar == section.bars - 1
            drums(b, section.drums, first, last, section.fill)
            bass(b, section.bass)
            guitar(b, section.guitar)
            keys(b, section.keys)
            lead(b, section.lead, scale)
            for beat in range(beats):
                i = bar * beats + beat
                if isinstance(section.tempo, tuple):
                    a, z = section.tempo
                    bpm = a + (z - a) * i / max(1, total_beats - 1)
                else:
                    bpm = section.tempo
                if section.rubato:
                    noise = 0.6 * noise + 0.8 * score.rnd.gauss(0, 1)
                    bpm *= 1 + section.rubato * max(-1.5, min(1.5, noise))
                    if beat == beats - 1 and bar % 2 == 1:
                        bpm *= 1 - section.rubato
                if song.drift:
                    bpm *= 1 + song.drift * math.sin(2 * math.pi * bar_index / song.drift_period_bars)
                if section.fermata and last and beat == beats - 1:
                    bpm /= 4
                score.tempos.append((position + beat * beat_len, bpm * beat_len))
            position += beats * beat_len
            bar_index += 1
    score.end = position  # type: ignore[attr-defined]
    return score


def write_midi(song: Song, score: Score, path: Path) -> None:
    midi = mido.MidiFile(ticks_per_beat=TPQ)
    tick = lambda q: int(round(q * TPQ))  # noqa: E731
    conductor = [(0, mido.MetaMessage("track_name", name=song.name, time=0))]
    last_tempo = None
    for q, bpm in score.tempos:
        tempo = mido.bpm2tempo(bpm)
        if tempo != last_tempo:
            conductor.append((tick(q), mido.MetaMessage("set_tempo", tempo=tempo, time=0)))
            last_tempo = tempo
    for q, (num, den) in score.meters:
        conductor.append((tick(q), mido.MetaMessage("time_signature", numerator=num, denominator=den, time=0)))
    for q, name in score.markers:
        conductor.append((tick(q), mido.MetaMessage("marker", text=name, time=0)))
    conductor.append((tick(score.end), mido.MetaMessage("end_of_track", time=0)))
    tracks = [conductor]
    for part, notes in score.notes.items():
        channel = CHANNELS[part]
        events = [(0, mido.MetaMessage("track_name", name=part, time=0))]
        if part != "drums":
            events.append((0, mido.Message("program_change", channel=channel, program=song.programs[part], time=0)))
        for start, length, pitch, velocity in notes:
            on = tick(start)
            events.append((on, mido.Message("note_on", channel=channel, note=pitch, velocity=velocity, time=0)))
            events.append((max(on + 1, tick(start + length)), mido.Message("note_off", channel=channel, note=pitch, velocity=0, time=0)))
        tracks.append(events)
    for events in tracks:
        # note_off before note_on at the same tick, so repeated notes are not cut
        events.sort(key=lambda e: (e[0], 0 if e[1].type in ("note_off", "set_tempo", "time_signature") else 1))
        track, now = mido.MidiTrack(), 0
        for t, msg in events:
            track.append(msg.copy(time=t - now))
            now = t
        midi.tracks.append(track)
    midi.save(path)


# --- the songs ----------------------------------------------------------------------------------

S = Section
SONGS = [
    Song("rock_120", "steady", [
        S("intro", 4, guitar="power", bass="eighths", chords=("E", "D", "A", "E")),
        S("verse", 8, guitar="power", chords=("E", "D", "A", "E")),
        S("chorus", 8, guitar="strum", keys="pad", lead="melody", chords=("A", "E", "D", "E")),
        S("verse", 8, guitar="power", chords=("E", "D", "A", "E")),
        S("chorus", 8, guitar="strum", keys="pad", lead="melody", chords=("A", "E", "D", "E")),
        S("outro", 4, guitar="sustain", bass="whole", drums="halftime", fermata=True, chords=("E",)),
    ], programs={"bass": 34, "guitar": 29, "keys": 48, "lead": 30}, seed=1),
    Song("ballad_75_feels", "feel changes", [
        S("intro", 4, tempo=75, drums="none", bass="none", guitar="arpeggio", keys="pad", chords=("Em", "C", "G", "D")),
        S("verse", 8, tempo=75, drums="rock", bass="half", guitar="arpeggio", lead="long", chords=("Em", "C", "G", "D")),
        S("chorus", 8, tempo=75, drums="rock", bass="quarters", guitar="arp16", keys="pad", lead="melody", chords=("C", "G", "D", "Em")),
        S("breakdown", 4, tempo=75, drums="none", bass="whole", guitar="none", keys="pad", lead="long", chords=("Am", "Em")),
        S("double", 8, tempo=75, drums="double", bass="eighths", guitar="power", lead="fast", chords=("Em", "C", "G", "D")),
        S("half", 4, tempo=75, drums="halftime", bass="half", guitar="arpeggio", lead="long", chords=("C", "D")),
        S("outro", 4, tempo=75, drums="none", bass="none", guitar="arpeggio", keys="pad", fermata=True, chords=("Em", "C", "Em", "Em")),
    ], programs={"bass": 33, "guitar": 27, "keys": 89, "lead": 30}, seed=2),
    Song("waltz_3-4_150", "3/4", [
        S("intro", 4, (3, 4), 150, drums="none", bass="none", guitar="none", keys="waltz", chords=("F", "C", "C", "F")),
        S("a", 16, (3, 4), 150, drums="waltz", bass="none", guitar="none", keys="waltz", lead="melody", chords=("F", "F", "C", "C", "Bb", "F", "C", "F")),
        S("b", 16, (3, 4), 150, drums="waltz", bass="none", guitar="arpeggio", keys="waltz", chords=("Dm", "Bb", "F", "C")),
        S("a", 12, (3, 4), 150, drums="waltz", bass="none", guitar="none", keys="waltz", lead="melody", fermata=True, chords=("F", "F", "C", "C", "Bb", "F")),
    ], programs={"bass": 32, "guitar": 24, "keys": 21, "lead": 73}, seed=3),
    Song("shuffle_12-8_70", "compound", [
        S("head", 12, (12, 8), 70, drums="shuffle", bass="quarters", guitar="shuffle", chords=("A", "A", "A", "A", "D", "D", "A", "A", "E", "D", "A", "E")),
        S("solo", 12, (12, 8), 70, drums="shuffle", bass="quarters", guitar="shuffle", lead="melody", chords=("A", "A", "A", "A", "D", "D", "A", "A", "E", "D", "A", "E")),
        S("end", 2, (12, 8), 70, drums="shuffle", bass="whole", guitar="sustain", fermata=True, chords=("A",)),
    ], programs={"bass": 33, "guitar": 26, "keys": 0, "lead": 29}, seed=4),
    Song("folk_6-8_66", "compound", [
        S("intro", 4, (6, 8), 66, drums="none", bass="none", guitar="fingerpick", chords=("D", "G", "D", "A")),
        S("verse", 16, (6, 8), 66, drums="rock", bass="quarters", guitar="fingerpick", lead="melody", chords=("D", "G", "D", "A")),
        S("chorus", 16, (6, 8), 66, drums="rock", bass="quarters", guitar="strum", keys="pad", chords=("G", "D", "A", "D")),
        S("outro", 4, (6, 8), 66, drums="none", bass="whole", guitar="fingerpick", fermata=True, chords=("D",)),
    ], programs={"bass": 32, "guitar": 25, "keys": 48, "lead": 22}, seed=5),
    Song("odd_5-4_110", "odd meter", [
        S("a", 16, (5, 4), 110, guitar="power", chords=("Dm", "Dm", "Bb", "C")),
        S("b", 8, (5, 4), 110, guitar="strum", keys="pad", lead="melody", chords=("F", "C", "Dm", "Bb")),
        S("a", 8, (5, 4), 110, guitar="power", fermata=True, chords=("Dm", "Dm", "Bb", "C")),
    ], programs={"bass": 34, "guitar": 29, "keys": 48, "lead": 81}, seed=6),
    Song("odd_7-4_130", "odd meter", [
        S("a", 12, (7, 4), 130, guitar="power", chords=("Em", "G")),
        S("b", 8, (7, 4), 130, guitar="strum", lead="melody", chords=("C", "D", "Em", "Em")),
        S("a", 8, (7, 4), 130, guitar="power", fermata=True, chords=("Em", "G")),
    ], programs={"bass": 34, "guitar": 30, "keys": 0, "lead": 81}, seed=7),
    Song("odd_bars_100", "odd bars", [
        S("intro", 4, tempo=100, chords=("G", "D", "Em", "C")),
        S("verse", 8, tempo=100, guitar="arpeggio", chords=("G", "D", "Em", "C")),
        S("chorus", 7, tempo=100, keys="pad", lead="melody", chords=("C", "G", "D", "Em"), fill=False),
        S("2/4 bar", 1, (2, 4), 100, chords=("D",)),
        S("verse", 8, tempo=100, guitar="arpeggio", chords=("G", "D", "Em", "C")),
        S("3/4 bar", 1, (3, 4), 100, chords=("D",)),
        S("chorus", 8, tempo=100, keys="pad", lead="melody", chords=("C", "G", "D", "Em")),
        S("6/4 bar", 1, (6, 4), 100, chords=("C",)),
        S("outro", 4, tempo=100, fermata=True, chords=("G", "D", "C", "G")),
    ], programs={"bass": 33, "guitar": 25, "keys": 4, "lead": 65}, seed=8),
    Song("tempo_jump", "tempo changes", [
        S("verse", 8, tempo=90, guitar="arpeggio", drums="rock", chords=("Am", "F", "C", "G")),
        S("chorus", 8, tempo=130, guitar="power", lead="melody", chords=("F", "G", "Am", "Am")),
        S("verse", 8, tempo=90, guitar="arpeggio", chords=("Am", "F", "C", "G")),
        S("chorus", 8, tempo=130, guitar="power", lead="melody", chords=("F", "G", "Am", "Am")),
        S("ritardando", 4, tempo=(130, 80), guitar="strum", fermata=True, chords=("F", "G", "Am", "Am")),
    ], programs={"bass": 34, "guitar": 29, "keys": 0, "lead": 30}, seed=9),
    Song("rubato_intro", "tempo changes", [
        S("intro", 8, tempo=72, rubato=0.12, drums="none", bass="none", guitar="none", keys="rubato_piano", chords=("C", "Am", "F", "G")),
        S("verse", 8, tempo=96, keys="piano", guitar="none", chords=("C", "Am", "F", "G")),
        S("chorus", 8, tempo=96, keys="piano", guitar="strum", lead="melody", chords=("F", "G", "C", "Am")),
        S("verse", 8, tempo=96, keys="piano", guitar="none", chords=("C", "Am", "F", "G")),
        S("outro", 4, tempo=(96, 66), drums="none", bass="whole", keys="rubato_piano", guitar="none", fermata=True, chords=("F", "G", "C", "C")),
    ], programs={"bass": 33, "guitar": 25, "keys": 0, "lead": 40}, seed=10),
    Song("funk_100", "syncopation", [
        S("groove", 16, tempo=100, drums="funk", bass="funk", guitar="scratch16", chords=("E", "E", "A", "E")),
        S("bridge", 8, tempo=100, drums="funk", bass="funk", guitar="scratch16", keys="pad", chords=("A", "B")),
        S("groove", 8, tempo=100, drums="funk", bass="funk", guitar="scratch16", lead="fast", chords=("E", "E", "A", "E")),
    ], programs={"bass": 36, "guitar": 28, "keys": 16, "lead": 81}, seed=11, humanize=0.7),
    Song("swing_160", "swing", [
        S("head", 32, tempo=160, drums="swing", bass="walking", guitar="none", keys="comp", lead="melody", chords=("Dm", "G", "C", "C", "Am", "D", "G", "G")),
        S("solo", 16, tempo=160, drums="swing", bass="walking", guitar="none", keys="comp", chords=("Dm", "G", "C", "C")),
    ], programs={"bass": 32, "guitar": 26, "keys": 0, "lead": 66}, seed=12, effects="jazz"),
    Song("metal_180", "feel changes", [
        S("riff", 16, tempo=180, drums="metal", guitar="power", bass="eighths", chords=("Em", "Em", "C", "D")),
        S("breakdown", 8, tempo=180, drums="metal_half", guitar="power", bass="eighths", chords=("Em", "F")),
        S("riff", 16, tempo=180, drums="metal", guitar="power", lead="fast", chords=("Em", "Em", "C", "D")),
        S("end", 2, tempo=180, drums="halftime", guitar="sustain", bass="whole", fermata=True, chords=("Em",)),
    ], programs={"bass": 34, "guitar": 30, "keys": 0, "lead": 30}, seed=13, effects="metal"),
    Song("acoustic_nodrums_85", "no drums", [
        S("a", 16, tempo=85, drums="none", bass="half", guitar="fingerpick", chords=("G", "Em", "C", "D")),
        S("b", 16, tempo=85, drums="none", bass="half", guitar="strum", lead="melody", chords=("C", "D", "G", "Em")),
        S("a", 8, tempo=85, drums="none", bass="half", guitar="fingerpick", fermata=True, chords=("G", "Em", "C", "D")),
    ], programs={"bass": 32, "guitar": 25, "keys": 0, "lead": 73}, seed=14, drift=0.03, humanize=1.5, effects="acoustic"),
    Song("live_drift_110", "tempo changes", [
        S("verse", 16, tempo=110, guitar="strum", chords=("D", "A", "Bm", "G")),
        S("chorus", 8, tempo=110, guitar="power", keys="pad", lead="melody", chords=("G", "A", "D", "D")),
        S("verse", 16, tempo=110, guitar="strum", chords=("D", "A", "Bm", "G")),
        S("chorus", 8, tempo=110, guitar="power", keys="pad", lead="melody", fermata=True, chords=("G", "A", "D", "D")),
    ], programs={"bass": 33, "guitar": 29, "keys": 16, "lead": 30}, seed=15, drift=0.05, drift_period_bars=12, humanize=2.0),
    Song("reggae_onedrop_75", "syncopation", [
        S("a", 16, tempo=75, drums="onedrop", bass="reggae", guitar="offbeat", keys="none", chords=("Am", "Am", "Dm", "Em")),
        S("b", 8, tempo=75, drums="onedrop", bass="reggae", guitar="offbeat", lead="melody", chords=("F", "G", "Am", "Am")),
        S("a", 8, tempo=75, drums="onedrop", bass="reggae", guitar="offbeat", chords=("Am", "Am", "Dm", "Em")),
    ], programs={"bass": 33, "guitar": 27, "keys": 16, "lead": 17}, seed=16),
    Song("stops_100", "stops", [
        S("groove", 4, tempo=100, chords=("A", "C", "D", "A")),
        S("stops", 4, tempo=100, drums="stops", bass="none", guitar="none", lead="long", chords=("A", "C", "D", "A")),
        S("groove", 4, tempo=100, chords=("A", "C", "D", "A")),
        S("silence", 1, tempo=100, drums="none", bass="none", guitar="none"),
        S("groove", 8, tempo=100, lead="melody", chords=("A", "C", "D", "A")),
        S("stops", 4, tempo=100, drums="stops", bass="none", guitar="none", chords=("D", "C", "A", "A")),
        S("groove", 4, tempo=100, fermata=True, chords=("A", "C", "D", "A")),
    ], programs={"bass": 33, "guitar": 29, "keys": 0, "lead": 30}, seed=17),
]


TEMPO_FACTORS = (1.0, 0.87, 1.15, 0.93, 1.07)


def variant(song: Song, index: int) -> Song:
    """The same song at another tempo, with other random choices."""
    if index == 0:
        return song
    factor = TEMPO_FACTORS[index % len(TEMPO_FACTORS)]

    def scaled(tempo: float | tuple[float, float]) -> float | tuple[float, float]:
        return (tempo[0] * factor, tempo[1] * factor) if isinstance(tempo, tuple) else tempo * factor

    sections = [replace(section, tempo=scaled(section.tempo)) for section in song.sections]
    return replace(song, name=f"{song.name}_v{index}", sections=sections, seed=song.seed + 100 * index)


def main() -> None:
    out = Path(sys.argv[1])
    variants = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out.mkdir(parents=True, exist_ok=True)
    for song in (variant(base, i) for base in SONGS for i in range(variants)):
        score = build(song)
        write_midi(song, score, out / f"{song.name}.mid")
        meta = {k: v for k, v in asdict(song).items() if k not in ("sections",)}
        meta["sections"] = [{"name": s.name, "bars": s.bars, "meter": s.meter, "tempo": s.tempo} for s in song.sections]
        (out / f"{song.name}.json").write_text(json.dumps(meta, indent=1))
        print(f"{song.name:22s} {song.category:14s} {sum(s.bars for s in song.sections):3d} bars")


if __name__ == "__main__":
    main()
