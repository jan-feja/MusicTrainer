"""Song structure test data and metrics, shared by the section-detection experiments.

Test sets (MT_DATA):
  harmonix  the downloaded Harmonix songs whose YouTube audio lines up with the annotations;
            in the training data of SongFormer and All-In-One: optimistic
  salami    SALAMI's Internet Archive part (live recordings, many genres; function labels by
            annotator 1, annotator 2 where there is one): in no tested model's training data
  score     the synthetic score songs (make_score_songs.py): exact section starts

Labels are mapped to seven classes, as in the SongFormer and All-In-One evaluations:
intro, verse (also pre-chorus), chorus (also post-chorus), bridge, inst (solo, instrumental,
interlude, break, ...), outro (also coda), silence (also end, applause, ...).

Metrics (mir_eval): HR.5F / HR3F boundary F-measure within 0.5 s / 3 s; PWF pairwise frame
F-measure (are repeated parts grouped alike); ACC share of time with the right class.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common import DATA

CLASSES = ("intro", "verse", "chorus", "bridge", "inst", "outro", "silence")
MANIFEST = Path(DATA, "structure", "manifest.json")
OUTPUTS = Path(DATA, "structure", "outputs")


@dataclass
class Song:
    set: str
    name: str
    audio: str
    starts: list[float]
    labels: list[str]
    """Raw labels, one per segment; segment i is [starts[i], starts[i+1]) and the last ends at `end`."""
    end: float
    labels2: list[str] | None = None
    starts2: list[float] | None = None


def map_label(label: str) -> str:
    """One of CLASSES for any annotation or model label."""
    l = re.sub(r"[\d_\-\s]+[a-z]?$", "", label.lower().strip()).replace("-", "").replace("_", "")
    l = re.sub(r"\d+$", "", l)
    if l in ("intro", "opening", "fadein", "introverse"):
        return "intro"
    if l in ("verse", "prechorus", "preverse", "postverse", "miniverse", "versepart", "raps", "rap", "head", "theme", "maintheme", "a", "groove"):
        return "verse"
    if l in ("chorus", "postchorus", "altchorus", "quietchorus", "intchorus", "refrain", "hook", "b"):
        return "chorus"
    if l in ("bridge", "c"):
        return "bridge"
    if l in ("outro", "coda", "fadeout", "ending", "end_section"):
        return "outro"
    if l in ("silence", "end", "start", "applause", "nofunction", "stagesounds", "crowdsounds",
             "spokenvoice", "stagespeaking", "voice", "pause", "&pause", "silent"):
        return "silence"
    if "chorus" in l:
        return "chorus"
    if "verse" in l:
        return "verse"
    return "inst"  # solo, inst(rumental), interlude, break(down), transition, riff, section, ...


# --- loading ---------------------------------------------------------------------------------


def _read_segments(path: Path) -> tuple[list[float], list[str], float]:
    """'time label' lines; the 'end' (or last) line closes the song."""
    rows = [line.split(None, 1) for line in path.read_text(encoding="utf8", errors="replace").splitlines() if line.strip()]
    times = [float(r[0]) for r in rows]
    labels = [r[1].strip() if len(r) > 1 else "" for r in rows]
    end = times[-1]
    if labels[-1].lower() in ("end", "end_section"):
        times, labels = times[:-1], labels[:-1]
    return times, labels, end


def aligned_shift(song: str) -> float | None:
    """Seconds to add to Harmonix annotation times for the YouTube audio (from the aligned beats)."""
    from common import harmonix_offset

    rows = np.loadtxt(Path(DATA, "harmonix", "ann", f"{song}.beats_and_downbeats.txt"))
    cache = Path(DATA, "harmonix", "aligned", f"{song}.json")
    data = json.loads(cache.read_text()) if cache.exists() else None
    if data is None:  # aligned by a constant shift instead
        return harmonix_offset(song, str(Path(DATA, "songs", f"{song}.wav")))
    beats, positions = np.array(data["beats"]), np.array(data["positions"])
    best = None
    for k in range(len(rows) - len(beats) + 1):
        if np.array_equal(rows[k : k + len(beats), 1].astype(int), positions):
            d = beats - rows[k : k + len(beats), 0]
            if best is None or np.std(d) < best[1]:
                best = (float(np.median(d)), float(np.std(d)))
    return None if best is None or best[1] > 0.5 else best[0]  # cut or warped songs: skip


def harmonix_songs() -> list[Song]:
    seg_dir = Path(DATA, "harmonix_full", "harmonixset-main", "dataset", "segments")
    out = []
    for wav in sorted(Path(DATA, "songs").glob("*.wav")):
        song = wav.stem
        if not (seg_dir / f"{song}.txt").exists() or not Path(DATA, "harmonix", "ann", f"{song}.beats_and_downbeats.txt").exists():
            continue
        shift = aligned_shift(song)
        if shift is None:
            continue
        starts, labels, end = _read_segments(seg_dir / f"{song}.txt")
        out.append(Song("harmonix", song, str(wav), [t + shift for t in starts], labels, end + shift))
    return out


def salami_songs() -> list[Song]:
    root = Path(DATA, "salami")
    out = []
    for audio in sorted((root / "audio").glob("*.mp3")):
        sid = audio.stem
        parsed = root / "salami-data-public" / "annotations" / sid / "parsed"
        starts, labels, end = _read_segments(parsed / "textfile1_functions.txt")
        song = Song("salami", sid, str(audio), starts, labels, end)
        second = parsed / "textfile2_functions.txt"
        if second.exists():
            s2, l2, _ = _read_segments(second)
            song.starts2, song.labels2 = s2, l2
        out.append(song)
    return out


def score_songs() -> list[Song]:
    """First variant of every score song: section starts from the MIDI markers (+1 s lead-in)."""
    import mido
    import pretty_midi

    out = []
    for folder in ("score_songs", "score_songs_changes"):
        for gt_path in sorted(Path(DATA, folder).glob("*/ground_truth.json")):
            name = gt_path.parent.name
            if re.search(r"_v\d$", name) or name == "bass":
                continue
            gt = json.loads(gt_path.read_text())
            midi_path = gt_path.parent / "song.mid"
            pm = pretty_midi.PrettyMIDI(str(midi_path))
            markers, tick = [], 0
            for msg in mido.merge_tracks(mido.MidiFile(str(midi_path)).tracks):
                tick += msg.time
                if msg.type == "marker":
                    markers.append((pm.tick_to_time(tick) + 1.0, msg.text))
            if len(markers) < 2:
                continue
            end = gt["beats"][-1] + 1.0
            out.append(Song("score", name, str(gt_path.parent / "mix.wav"),
                            [0.0] + [t for t, _ in markers], ["silence"] + [m for _, m in markers], end))
    return out


def write_manifest(sets=("harmonix", "salami", "score")) -> list[Song]:
    songs = []
    if "harmonix" in sets:
        songs += harmonix_songs()
    if "salami" in sets:
        songs += salami_songs()
    if "score" in sets:
        songs += score_songs()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps([s.__dict__ for s in songs], indent=1))
    return songs


def load_manifest() -> list[Song]:
    return [Song(**row) for row in json.loads(MANIFEST.read_text())]


def output_path(method: str, song: Song) -> Path:
    return OUTPUTS / method / f"{song.set}__{song.name}.json"


def read_output(method: str, song: Song) -> tuple[list[float], list[str], float] | None:
    """A method's segments: JSON list of {start, end, label}."""
    path = output_path(method, song)
    if not path.exists():
        return None
    segments = json.loads(path.read_text())
    if not segments:
        return None
    return [s["start"] for s in segments], [s["label"] for s in segments], segments[-1]["end"]


# --- metrics ---------------------------------------------------------------------------------


def intervals(starts: list[float], end: float) -> np.ndarray:
    edges = list(starts) + [end]
    out = np.array([[a, b] for a, b in zip(edges[:-1], edges[1:]) if b > a])
    return out if len(out) else np.array([[0.0, end]])


def _clip(starts, labels, end, length):
    """Segments cut / extended to [0, length) (mir_eval wants the same span for both)."""
    pairs = []
    for s, l in zip(starts, labels):
        s = max(0.0, s)  # aligned annotations can start before the audio
        if s >= length:
            break
        if pairs and s <= pairs[-1][0]:
            pairs[-1] = (pairs[-1][0], l)
        else:
            pairs.append((s, l))
    if not pairs or pairs[0][0] > 0:
        pairs = [(0.0, "silence")] + pairs
    s, l = zip(*pairs)
    return list(s), list(l), length


def evaluate(ref: tuple, est: tuple, functional: bool = True) -> dict:
    """ref, est: (starts, labels, end). functional=False: the estimate's labels only say which
    parts repeat (A, B, ...): pairwise F uses them as they are and ACC is left out."""
    import mir_eval

    length = max(ref[2], 1.0)
    rs, rl, _ = _clip(*ref, length)
    es, el, _ = _clip(*est, length)
    ri, ei = intervals(rs, length), intervals(es, length)
    rl, el = rl[: len(ri)], el[: len(ei)]
    row = {}
    for window, key in ((0.5, "HR.5F"), (3.0, "HR3F")):
        row[key] = mir_eval.segment.detection(ri, ei, window=window, trim=True)[2]
    rmap, emap = [map_label(l) for l in rl], [map_label(l) if functional else l for l in el]
    row["PWF"] = mir_eval.segment.pairwise(ri, rmap, ei, emap)[2]
    if not functional:
        return row
    times = np.arange(0, length, 0.1)
    def at(intv, labs):
        idx = np.clip(np.searchsorted(intv[:, 0], times, side="right") - 1, 0, len(labs) - 1)
        return np.array(labs)[idx]
    row["ACC"] = float(np.mean(at(ri, rmap) == at(ei, emap)))
    return row


def evaluate_method(method: str, songs: list[Song]) -> dict:
    rows = {}
    for song in songs:
        est = read_output(method, song)
        if est is None:
            continue
        rows[f"{song.set}/{song.name}"] = evaluate((song.starts, song.labels, song.end), est)
    return rows


def summarize(rows: dict) -> dict:
    out = {}
    for set_name in sorted({k.split("/")[0] for k in rows}):
        members = [v for k, v in rows.items() if k.startswith(set_name + "/")]
        if members:
            out[set_name] = {m: round(float(np.mean([r[m] for r in members])), 3) for m in members[0]} | {"songs": len(members)}
    return out
