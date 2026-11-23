"""Transcribed notes -> notation: notes placed in bars and beats, written as a Guitar Pro 5 file.

1. Every onset gets a position in beats, by interpolating between the song's beats (so tempo
   changes and drift follow the recording).
2. Per beat, the onsets snap to sixteenths or to eighth-note triplets, whichever fits clearly
   better (triplets must halve the timing error: straight rhythms are far more common).
3. A note lasts until its quantized end, at most until the next onset of the part when the part
   is monophonic (bass, lead), and at least one grid step; a gap of up to an eighth note before
   the next onset is filled (articulation, not a rest worth writing).
4. Bars come from the bar starts; a bar has as many quarter-note beats as were detected in it.
5. Guitar and bass get strings and frets from tablature.assign_frets; drums go on a percussion
   track; other parts on a track with a wide, keyboard-like range (shown as notation).

Writes Guitar Pro 5 (pyguitarpro), which alphaTab renders as tab + standard notation.
"""

from dataclasses import dataclass

import numpy as np

import tablature as tab

TICKS = 960  # Guitar Pro ticks per quarter note
UNIT = 12  # quantization units per beat: sixteenths are 3 units, triplet eighths 4
TRIPLET_GAIN = 0.5  # triplets must halve the mean timing error


@dataclass
class QNote:
    start: int  # position in units (UNIT per beat) from the first beat
    end: int
    pitch: int
    string: int = -1
    fret: int = -1


def beat_position(times: np.ndarray, beats: np.ndarray) -> np.ndarray:
    """Fractional beat index of each time (linear extrapolation outside the beats)."""
    idx = np.arange(len(beats), dtype=float)
    pos = np.interp(times, beats, idx)
    first, last = beats[1] - beats[0], beats[-1] - beats[-2]
    pos = np.where(times < beats[0], (times - beats[0]) / first, pos)
    return np.where(times > beats[-1], len(beats) - 1 + (times - beats[-1]) / last, pos)


def quantize(notes: list[tuple[float, float, int]], beats: np.ndarray, monophonic: bool = False) -> list[QNote]:
    """(onset, offset, pitch) in seconds -> QNotes on the beat grid."""
    if not notes:
        return []
    on = beat_position(np.array([n[0] for n in notes]), beats)
    off = beat_position(np.array([n[1] for n in notes]), beats)
    owner = np.floor(on + 1 / 8).astype(int)  # an onset just before a beat belongs to that beat
    starts = np.zeros(len(notes), dtype=int)
    for b in np.unique(owner):
        members = np.flatnonzero(owner == b)
        frac = on[members] - b
        err16 = np.abs(frac * 4 - np.round(frac * 4)) / 4
        err3 = np.abs(frac * 3 - np.round(frac * 3)) / 3
        triplet = len(members) >= 2 and err3.mean() < TRIPLET_GAIN * err16.mean()
        steps = 3 if triplet else 4
        starts[members] = b * UNIT + np.round(frac * steps).astype(int) * (UNIT // steps)
    ends = np.maximum(np.round(off * 4).astype(int) * (UNIT // 4), starts + UNIT // 4)
    out = sorted((QNote(int(s), int(e), int(n[2])) for s, e, n in zip(starts, ends, notes)), key=lambda q: (q.start, q.pitch))
    # a short gap before the next onset is articulation, not a rest worth writing
    onsets = sorted({q.start for q in out})
    for q in out:
        k = np.searchsorted(onsets, q.start, side="right")
        if k < len(onsets) and 0 < onsets[k] - q.end <= UNIT // 2:
            q.end = onsets[k]
    if monophonic:
        dedup = []
        for q in out:  # one note per onset (the lowest for bass-like parts is kept by sort order)
            if dedup and dedup[-1].start == q.start:
                continue
            dedup.append(q)
        out = dedup
        for a, b in zip(out[:-1], out[1:]):
            a.end = min(a.end, b.start)
    return out


def bar_lengths(beats: np.ndarray, downbeats: np.ndarray) -> list[tuple[int, int]]:
    """(first beat index, beats in bar) for every bar; beats before the first bar start form a pickup bar."""
    starts = sorted({int(np.argmin(np.abs(beats - d))) for d in downbeats})
    if not starts or starts[0] > 0:
        starts = [0] + starts
    bars = [(a, b - a) for a, b in zip(starts[:-1], starts[1:]) if b > a]
    last = starts[-1]
    typical = int(np.median([n for _, n in bars])) if bars else 4
    bars.append((last, typical))
    return bars


# --- Guitar Pro output -----------------------------------------------------------------------

# (units, Guitar Pro duration value, dotted, triplet), longest first
DURATIONS = [(48, 1, False, False), (36, 2, True, False), (24, 2, False, False), (18, 4, True, False),
             (12, 4, False, False), (9, 8, True, False), (8, 4, False, True), (6, 8, False, False),
             (4, 8, False, True), (3, 16, False, False), (2, 16, False, True), (1, 32, False, True)]


def _pieces(start: int, length: int) -> list[tuple[int, int, bool, bool]]:
    """Split a span into note values, never crossing a beat with a triplet or an odd position."""
    out = []
    pos, left = start, length
    while left > 0:
        for units, value, dotted, triplet in DURATIONS:
            if units > left:
                continue
            in_beat = pos % UNIT
            if units >= UNIT and in_beat:  # long values start on a beat
                continue
            if units < UNIT and in_beat + units > UNIT:  # short values stay inside their beat
                continue
            if triplet and in_beat % 4:
                continue
            if not triplet and units < UNIT and in_beat % 3:
                continue
            out.append((units, value, dotted, triplet))
            pos += units
            left -= units
            break
        else:  # odd remainder (1 unit): absorb it
            pos += left
            left = 0
    return out


def write_gp5(path: str, parts: list[dict], beats: np.ndarray, downbeats: np.ndarray, title: str = "Transcription") -> None:
    """parts: [{"name", "kind" (guitar | bass | drums | keys), "notes": [QNote], "program"}]"""
    import guitarpro
    from guitarpro import models as gm

    bars = bar_lengths(beats, downbeats)
    song = gm.Song()
    song.title = title
    song.tempo = int(round(60 / np.median(np.diff(beats))))
    song.measureHeaders = []
    for i, (_, n_beats) in enumerate(bars):
        header = gm.MeasureHeader()
        header.number = i + 1
        header.start = TICKS + sum(n for _, n in bars[:i]) * TICKS
        header.timeSignature.numerator = n_beats
        header.timeSignature.denominator.value = 4
        song.addMeasureHeader(header)
    song.tracks = []
    tunings = {"guitar": tab.STANDARD, "bass": tab.BASS_STANDARD, "keys": (36, 43, 50, 57, 64, 71), "drums": (0,) * 6}
    for t, part in enumerate(parts):
        kind = part["kind"]
        channel = gm.MidiChannel(channel=9 if kind == "drums" else t, effectChannel=9 if kind == "drums" else t,
                                 instrument=part.get("program", 0))
        track = gm.Track(song, number=t + 1, name=part["name"], isPercussionTrack=kind == "drums", channel=channel,
                         fretCount=24 if kind != "keys" else 40)
        tuning = tunings[kind]
        track.strings = [gm.GuitarString(i + 1, v) for i, v in enumerate(sorted(tuning, reverse=True))]
        notes = part["notes"]
        if kind in ("guitar", "bass"):
            # the fingering search works in seconds (chord window, pauses): use the median tempo
            sec_per_unit = float(np.median(np.diff(beats))) / UNIT
            sec = [(q.start * sec_per_unit, q.end * sec_per_unit, q.pitch) for q in notes]
            frets = {(round(n.onset / sec_per_unit), n.pitch): n for n in tab.assign_frets(sec, tuning=tuning)}
            for q in notes:
                f = frets.get((q.start, q.pitch))
                if f:
                    q.string, q.fret = len(tuning) - f.string, f.fret  # Guitar Pro: string 1 = highest
        elif kind == "keys":
            for q in notes:
                opts = [(len(tuning) - s, q.pitch - o) for s, o in enumerate(tuning) if 0 <= q.pitch - o <= 40]
                if opts:
                    q.string, q.fret = min(opts, key=lambda x: x[1])
        else:
            for q in notes:
                q.string, q.fret = 1, q.pitch
        by_start: dict[int, list[QNote]] = {}
        for q in notes:
            if q.string > 0:
                by_start.setdefault(q.start, []).append(q)
        track.measures = []
        for (first_beat, n_beats), header in zip(bars, song.measureHeaders):
            measure = gm.Measure(track, header)
            voice = measure.voices[0]
            voice.beats = []
            bar_start, bar_end = first_beat * UNIT, (first_beat + n_beats) * UNIT
            onsets = sorted(s for s in by_start if bar_start <= s < bar_end)
            events = []  # (start, length, notes or None for a rest)
            pos = bar_start
            for k, s in enumerate(onsets):
                if s > pos:
                    events.append((pos, s - pos, None))
                nxt = onsets[k + 1] if k + 1 < len(onsets) else bar_end
                length = max(min(max(q.end for q in by_start[s]), nxt) - s, 1)
                events.append((s, length, by_start[s]))
                if nxt > s + length:
                    events.append((s + length, nxt - s - length, None))
                pos = nxt
            if pos < bar_end and not onsets:
                events.append((pos, bar_end - pos, None))
            for start, length, chord in events:
                for i, (units, value, dotted, triplet) in enumerate(_pieces(start, length)):
                    beat = gm.Beat(voice)
                    beat.duration = gm.Duration(value=value, isDotted=dotted,
                                                tuplet=gm.Tuplet(3, 2) if triplet else gm.Tuplet(1, 1))
                    if chord is None:
                        beat.status = gm.BeatStatus.rest
                    else:
                        beat.status = gm.BeatStatus.normal
                        strings_here = set()
                        for k, q in enumerate(chord):
                            if kind == "drums":  # hits at once go on separate lines; no ties
                                if i > 0 or k >= 6 or q.pitch in strings_here:
                                    continue
                                strings_here.add(q.pitch)
                                beat.notes.append(gm.Note(beat, value=q.pitch, string=len(strings_here)))
                                continue
                            if q.string in strings_here:
                                continue
                            strings_here.add(q.string)
                            beat.notes.append(gm.Note(beat, value=q.fret, string=q.string,
                                                      type=gm.NoteType.tie if i > 0 else gm.NoteType.normal))
                        if not beat.notes:
                            beat.status = gm.BeatStatus.rest
                    voice.beats.append(beat)
            track.measures.append(measure)
        song.tracks.append(track)
    guitarpro.write(song, path, version=(5, 1, 0))

