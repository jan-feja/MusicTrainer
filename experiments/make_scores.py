"""MIDI -> notation: write the synthetic bass line as a Guitar Pro 5 tab and as MusicXML.

Shows the step "transcribed / imported MIDI notes -> tab the player can read".
Fret choice is a simple rule (stay close to the previous hand position); real
tab tools use smarter fingering search.

Usage: python make_scores.py [midi_path]  (default: synthetic bass, ground truth)
"""
import os
import sys

import guitarpro
import pretty_midi

from common import DATA, synth_dir

OUT = os.path.join(DATA, "scores")
BASS_TUNING = [43, 38, 33, 28]  # G2 D2 A1 E1 (string 1 = highest)
TICKS_8TH = 480  # Guitar Pro: quarter = 960 ticks


def choose_fret(pitch, prev_fret):
    options = [(s + 1, pitch - open_) for s, open_ in enumerate(BASS_TUNING) if 0 <= pitch - open_ <= 20]
    if not options:
        return None
    return min(options, key=lambda o: abs(o[1] - prev_fret) + 0.1 * o[1])


def midi_to_gp5(midi_path, out_path, bpm=100.0, start_offset=0.5, title="Bass line"):
    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = sorted(pm.instruments[0].notes, key=lambda n: n.start)
    eighth = 60.0 / bpm / 2
    # quantise to an 8th-note grid
    grid = {}
    for n in notes:
        k = round((n.start - start_offset) / eighth)
        grid.setdefault(k, n.pitch)
    n_bars = max(grid) // 8 + 1

    song = guitarpro.models.Song()
    song.title = title
    song.tempo = int(bpm)
    track = song.tracks[0]
    track.name = "Bass"
    track.channel.instrument = 33
    track.strings = [guitarpro.models.GuitarString(i + 1, v) for i, v in enumerate(BASS_TUNING)]
    # add measure headers
    while len(song.measureHeaders) < n_bars:
        header = guitarpro.models.MeasureHeader()
        song.addMeasureHeader(header)
    for h in song.measureHeaders:
        h.timeSignature.numerator = 4
        h.timeSignature.denominator.value = 4
    track.measures = [guitarpro.models.Measure(track, h) for h in song.measureHeaders]
    prev = 5
    for bar in range(n_bars):
        voice = track.measures[bar].voices[0]
        voice.beats = []
        for k in range(bar * 8, bar * 8 + 8):
            beat = guitarpro.models.Beat(voice)
            beat.duration = guitarpro.models.Duration(value=8)
            if k in grid and (sf := choose_fret(grid[k], prev)):
                string, fret = sf
                prev = fret
                beat.notes.append(guitarpro.models.Note(beat, value=fret, string=string,
                                                        type=guitarpro.models.NoteType.normal))
                beat.status = guitarpro.models.BeatStatus.normal
            else:
                beat.status = guitarpro.models.BeatStatus.rest
            voice.beats.append(beat)
    guitarpro.write(song, out_path, version=(5, 1, 0))
    return n_bars


def midi_to_musicxml(midi_path, out_path):
    import music21
    s = music21.converter.parse(midi_path, quantizePost=True, quarterLengthDivisors=(4, 3))
    s.metadata = music21.metadata.Metadata(title="Synthetic song (from MIDI)")
    s.write("musicxml", fp=out_path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(synth_dir("steady"), "bass.mid")
    bars = midi_to_gp5(src, os.path.join(OUT, "bass.gp5"))
    print("wrote bass.gp5,", bars, "bars")
    midi_to_musicxml(os.path.join(synth_dir("steady"), "song.mid"), os.path.join(OUT, "song.musicxml"))
    print("wrote song.musicxml")
