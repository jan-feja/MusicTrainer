"""Render scores to audio with exact beat and bar ground truth.

Input: MIDI files (.mid) or Guitar Pro 3/4/5 tabs (.gp3, .gp4, .gp5), or folders
of them. Guitar Pro tabs are first converted to MIDI (repeats and alternate
endings played out, tempo changes, time signatures, triplet feel, capo).

For every score, <out_dir>/<name>/ gets:
  song.mid            the MIDI that was rendered (for Guitar Pro: the conversion)
  mix.wav             44.1 kHz stereo mix
  ground_truth.json   beats and downbeats (seconds), time signatures, tempo range,
                      category (from the <name>.json sidecar of make_score_songs.py)

Beats come from the score: one per denominator note, except compound meters
(6/8, 9/8, 12/8) where a beat is a dotted quarter (unless the sidecar sets
eighth_beats, for songs that mix 6/8 with 5/8 or 7/8 bars: then every eighth is a beat). Beats before the first note
and after the last note onset are left out (nothing to hear there).

Rendering: every part separately with FluidSynth, small random timing jitter
(players are never exactly on the grid; the ground truth stays on the grid),
effects per instrument family with pedalboard, then a compressed mix.

Usage: python score_to_audio.py <out_dir> <score files or folders ...>
Needs env vars FLUIDSYNTH (fluidsynth executable) and SOUNDFONT (.sf2).
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mido
import numpy as np
import pretty_midi
import soundfile as sf

SR = 44100
LEAD_IN = 1.0  # seconds of silence before the music, as in most recordings
TAIL = 2.5  # seconds kept after the last note ends
GP_SUFFIXES = {".gp3", ".gp4", ".gp5"}
MIDI_SUFFIXES = {".mid", ".midi"}
GP_QUARTER = 960  # Guitar Pro ticks per quarter note


# --- Guitar Pro -> MIDI --------------------------------------------------------------------------


def playback_order(headers) -> list[int]:
    """Measure indices in playing order: repeats and alternate endings played out."""
    order, i, repeat_start, pass_number = [], 0, 0, 1
    done: dict[int, int] = {}
    while i < len(headers):
        header = headers[i]
        if header.isRepeatOpen and i != repeat_start:
            repeat_start, pass_number = i, 1
        if header.repeatAlternative and not (header.repeatAlternative >> (pass_number - 1)) & 1:
            i += 1
            continue
        order.append(i)
        if header.repeatClose > 0 and done.get(i, 0) < header.repeatClose:
            done[i] = done.get(i, 0) + 1
            pass_number += 1
            i = repeat_start
            continue
        if header.repeatClose > 0:
            done[i] = 0
            repeat_start, pass_number = i + 1, 1
        i += 1
    return order


def gp_to_midi(path: Path, target: Path) -> None:
    import guitarpro

    song = guitarpro.parse(str(path))
    headers = song.measureHeaders
    order = playback_order(headers)
    starts, now = [], GP_QUARTER  # one quarter of silence at the start
    for idx in order:
        starts.append(now)
        now += headers[idx].length
    end = now

    conductor = [(0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo)))]
    last_meter = None
    for idx, start in zip(order, starts):
        ts = headers[idx].timeSignature
        meter = (ts.numerator, ts.denominator.value)
        if meter != last_meter:
            conductor.append((start, mido.MetaMessage("time_signature", numerator=meter[0], denominator=meter[1])))
            last_meter = meter

    tracks = []
    tempo_changes: list[tuple[int, float, int]] = []  # (tick, bpm, ramp length in quarters)
    for track_index, track in enumerate(song.tracks):
        channel = 9 if track.isPercussionTrack else min(track.channel.channel, 15)
        if channel == 9 and not track.isPercussionTrack:
            channel = 8
        events = [(0, mido.MetaMessage("track_name", name=track.name or f"track {track_index + 1}"))]
        if not track.isPercussionTrack:
            events.append((0, mido.Message("program_change", channel=channel, program=track.channel.instrument % 128)))
        open_notes: dict[int, list] = {}  # string -> [pitch, on tick, off tick, velocity]
        notes = []
        for idx, bar_start in zip(order, starts):
            header, measure = headers[idx], track.measures[idx]
            shift = bar_start - header.start
            swing = header.tripletFeel.name == "eighth"
            for voice in measure.voices:
                for beat in voice.beats:
                    on, length = beat.start + shift, beat.duration.time
                    if swing and length == GP_QUARTER // 2:
                        if (beat.start - header.start) % GP_QUARTER == GP_QUARTER // 2:
                            on, length = on + GP_QUARTER // 6, length - GP_QUARTER // 6
                        elif (beat.start - header.start) % GP_QUARTER == 0:
                            length += GP_QUARTER // 6
                    mix = beat.effect.mixTableChange
                    if track_index == 0 and mix is not None and mix.tempo is not None and mix.tempo.value > 0:
                        tempo_changes.append((on, float(mix.tempo.value), mix.tempo.duration))
                    for note in beat.notes:
                        if note.type.name == "tie" and note.string in open_notes:
                            open_notes[note.string][2] = on + length
                            continue
                        if note.type.name == "rest":
                            continue
                        if track.isPercussionTrack:
                            pitch = note.value
                        else:
                            pitch = note.realValue + track.offset
                        dead = note.type.name == "dead"
                        entry = [pitch, on, on + (length // 4 if dead else length), note.velocity if not dead else 50]
                        if note.string in open_notes:
                            notes.append(open_notes.pop(note.string))
                        open_notes[note.string] = entry
        notes.extend(open_notes.values())
        for pitch, on, off, velocity in notes:
            if 0 <= pitch < 128:
                events.append((on, mido.Message("note_on", channel=channel, note=pitch, velocity=max(1, min(127, velocity)))))
                events.append((max(on + 1, off), mido.Message("note_off", channel=channel, note=pitch, velocity=0)))
        tracks.append(events)

    current = float(song.tempo)
    for tick, bpm, ramp in sorted(tempo_changes):
        if ramp > 0:  # gradual change over `ramp` beats, one step per quarter
            for k in range(1, ramp + 1):
                conductor.append((tick + (k - 1) * GP_QUARTER, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(current + (bpm - current) * k / ramp))))
        else:
            conductor.append((tick, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))))
        current = bpm
    conductor.append((end, mido.MetaMessage("marker", text="end")))
    write_tracks([conductor] + tracks, GP_QUARTER, target)


def write_tracks(tracks: list[list[tuple[int, mido.Message]]], ticks_per_quarter: int, target: Path) -> None:
    midi = mido.MidiFile(ticks_per_beat=ticks_per_quarter)
    for events in tracks:
        events.sort(key=lambda e: (e[0], 0 if e[1].type in ("note_off", "set_tempo", "time_signature") else 1))
        track, now = mido.MidiTrack(), 0
        for tick, msg in events:
            track.append(msg.copy(time=tick - now))
            now = tick
        midi.tracks.append(track)
    midi.save(target)


# --- ground truth ---------------------------------------------------------------------------------


def score_grid(pm: pretty_midi.PrettyMIDI, end_tick: int, eighth_beats: bool = False) -> tuple[list[float], list[float], list[dict]]:
    """Beats, bar starts (seconds) and time signatures, from the tempo map and meters."""
    resolution = pm.resolution
    signatures = sorted(pm.time_signature_changes, key=lambda ts: ts.time) or [pretty_midi.TimeSignature(4, 4, 0.0)]
    changes = [(pm.time_to_tick(ts.time), ts.numerator, ts.denominator) for ts in signatures]
    beats, downbeats, meters = [], [], []
    for i, (tick, num, den) in enumerate(changes):
        stop = changes[i + 1][0] if i + 1 < len(changes) else end_tick
        compound = den == 8 and num % 3 == 0 and num > 3 and not eighth_beats
        beat_ticks = resolution * 4 / den * (3 if compound else 1)
        per_bar = num // 3 if compound else num
        meters.append({"time": pm.tick_to_time(tick) + LEAD_IN, "numerator": num, "denominator": den, "beats_per_bar": per_bar})
        t = float(tick)
        while t < stop - 1e-6:
            for b in range(per_bar):
                position = t + b * beat_ticks
                if position >= stop - 1e-6:
                    break
                seconds = pm.tick_to_time(int(round(position)))
                beats.append(seconds)
                if b == 0:
                    downbeats.append(seconds)
            t += per_bar * beat_ticks
    return beats, downbeats, meters


# --- rendering --------------------------------------------------------------------------------------

JITTER = {"drums": 0.004, "bass": 0.007, "guitar": 0.009, "keys": 0.008, "lead": 0.012}


def family(inst: pretty_midi.Instrument) -> str:
    if inst.is_drum:
        return "drums"
    p = inst.program
    if 32 <= p <= 39:
        return "bass"
    if 24 <= p <= 31:
        return "guitar"
    if p in range(40, 56) or p in range(88, 104) or p < 24:
        return "keys"
    return "lead"


def effects(fam: str, program: int, preset: str, rnd: random.Random):
    from pedalboard import Chorus, Compressor, Delay, Distortion, HighpassFilter, LowpassFilter, Pedalboard, Reverb

    room = {"jazz": 0.5, "acoustic": 0.45}.get(preset, 0.3)
    if fam == "drums":
        return Pedalboard([Compressor(threshold_db=-20, ratio=3), Reverb(room_size=room * 0.6, wet_level=0.08)])
    if fam == "bass":
        return Pedalboard([Compressor(threshold_db=-22, ratio=4), LowpassFilter(3000)])
    if fam == "guitar" and program in (29, 30, 31):
        drive = rnd.uniform(18, 26) if preset == "metal" else rnd.uniform(8, 16)
        return Pedalboard([Distortion(drive_db=drive), HighpassFilter(90), LowpassFilter(6500), Reverb(room_size=room, wet_level=0.1)])
    if fam == "guitar":
        return Pedalboard([Chorus(rate_hz=0.8, depth=0.15, mix=0.3), Reverb(room_size=room, wet_level=0.15)])
    if fam == "lead":
        return Pedalboard([Delay(delay_seconds=rnd.uniform(0.25, 0.4), feedback=0.25, mix=0.15), Reverb(room_size=0.5, wet_level=0.2)])
    return Pedalboard([Reverb(room_size=room + 0.1, wet_level=0.2)])


LOUDNESS_DB = {"drums": -16, "bass": -20, "guitar": -20, "keys": -24, "lead": -19}


def render(midi_path: Path, out_dir: Path, meta: dict, seed: int) -> dict:
    from pedalboard import Compressor, Limiter, Pedalboard

    fluidsynth, soundfont = os.environ["FLUIDSYNTH"], os.environ["SOUNDFONT"]
    rnd = random.Random(seed)
    np_rnd = np.random.default_rng(seed)
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    humanize = float(meta.get("humanize", 1.0))
    preset = meta.get("effects", "band")
    stems = []
    with tempfile.TemporaryDirectory() as tmp:
        for k, inst in enumerate(pm.instruments):
            if not inst.notes:
                continue
            fam = family(inst)
            part = pretty_midi.PrettyMIDI(resolution=pm.resolution, initial_tempo=120)
            copy = pretty_midi.Instrument(inst.program, is_drum=inst.is_drum, name=inst.name)
            lag = 0.0 if fam == "drums" else rnd.uniform(-0.004, 0.010) * humanize
            for n in inst.notes:
                jitter = float(np_rnd.normal(0, JITTER[fam] * humanize)) + lag
                start = max(0.0, n.start + jitter)
                copy.notes.append(pretty_midi.Note(n.velocity, n.pitch, start, max(start + 0.03, n.end + jitter)))
            part.instruments.append(copy)
            mid, wav = Path(tmp) / f"{k}.mid", Path(tmp) / f"{k}.wav"
            part.write(str(mid))
            subprocess.run([fluidsynth, "-ni", "-q", "-g", "0.5", "-r", str(SR), "-F", str(wav), soundfont, str(mid)],
                           check=True, capture_output=True)
            audio, _ = sf.read(wav, dtype="float32", always_2d=True)
            audio = effects(fam, inst.program, preset, rnd)(audio.T.copy(), SR).T
            rms = np.sqrt(np.mean(audio**2)) + 1e-9
            target = 10 ** ((LOUDNESS_DB[fam] + rnd.uniform(-2, 2)) / 20)
            stems.append(audio * target / rms)
    n = max(len(s) for s in stems)
    mix = sum(np.pad(s, ((0, n - len(s)), (0, 0))) for s in stems)
    music_end = max(note.end for inst in pm.instruments for note in inst.notes)
    mix = np.concatenate([np.zeros((int(LEAD_IN * SR), 2), dtype=mix.dtype), mix[: int((music_end + TAIL) * SR)]])
    mix = Pedalboard([Compressor(threshold_db=-14, ratio=2.5), Limiter(threshold_db=-1.0)])(mix.T.copy(), SR).T
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.89
    sf.write(out_dir / "mix.wav", mix, SR, subtype="PCM_16")
    return {"seconds": round(len(mix) / SR, 2)}


def ground_truth(midi_path: Path, eighth_beats: bool = False) -> dict:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    onsets = sorted(n.start for inst in pm.instruments for n in inst.notes)
    end_tick = max(pm.time_to_tick(max(n.end for inst in pm.instruments for n in inst.notes)), 1) + pm.resolution
    beats, downbeats, meters = score_grid(pm, end_tick, eighth_beats)
    first, last = onsets[0] - 0.07, onsets[-1] + 0.07
    keep = lambda times: [round(t + LEAD_IN, 5) for t in times if first <= t <= last]  # noqa: E731
    beats_kept = keep(beats)
    intervals = np.diff(beats_kept)
    return {
        "beats": beats_kept,
        "downbeats": keep(downbeats),
        "meters": meters,
        "bpm_min": round(float(60 / intervals.max()), 2) if len(intervals) else None,
        "bpm_max": round(float(60 / intervals.min()), 2) if len(intervals) else None,
    }


def collect(paths: list[str]) -> list[Path]:
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in GP_SUFFIXES | MIDI_SUFFIXES)
        else:
            files.append(p)
    return files


def main() -> None:
    out_root = Path(sys.argv[1])
    for i, score in enumerate(collect(sys.argv[2:])):
        out = out_root / score.stem
        out.mkdir(parents=True, exist_ok=True)
        midi = out / "song.mid"
        if score.suffix.lower() in GP_SUFFIXES:
            gp_to_midi(score, midi)
            source = "guitar pro"
        else:
            shutil.copy(score, midi)
            source = "midi"
        sidecar = score.with_suffix(".json")
        meta = json.loads(sidecar.read_text()) if sidecar.exists() else {"category": "other"}
        gt = ground_truth(midi, bool(meta.get("eighth_beats")))
        gt.update({"name": score.stem, "source": source, "category": meta.get("category", "other")})
        gt.update(render(midi, out, meta, seed=1000 + i))
        (out / "ground_truth.json").write_text(json.dumps(gt, indent=1))
        meters = sorted({f"{m['numerator']}/{m['denominator']}" for m in gt["meters"]})
        print(f"{score.stem:24s} {gt['seconds']:6.1f} s  {len(gt['beats']):4d} beats {len(gt['downbeats']):3d} bars  "
              f"meters {','.join(meters)}  bpm {gt['bpm_min']}-{gt['bpm_max']}", flush=True)


if __name__ == "__main__":
    main()
