"""Notes -> notation: does quantizing to the beat grid put notes at the score's positions?

Score songs rendered with stems (render_score_stems.py): every note has a true position in the
score (beat index + fraction). notation.quantize places the played notes on the grid; a note is
"right in the notation" when it was transcribed (pitch right, onset within 70 ms of the score
time) and quantized to exactly its score position (sixteenth / triplet units).

Inputs: the true played notes (with the renderer's timing jitter: quantization alone), YourMT3+
on the mix, htdemucs_6s + Basic Pitch (see test_multitrack.py).
Grids: the score's own beats, and Beat This! beats (test_structure.py beats); with detected beats
the beat numbering is aligned to the score by the first beat, and songs where the detected tempo is
off by a factor (double / half time) count as all wrong.

Metric per family: notation F (precision / recall of notes right in the notation); of the
transcribed notes, the share with the right position, and the share with the right place within
the beat (the rhythm figure, even when the beat numbering drifted).
Grids also include the app's own (Beat This! + the app's decoder, test_structure.py app-beats).

Usage: python test_notation.py      (writes results/notation.json)
"""

import json
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

import notation
from common import DATA, save_result
from score_to_audio import LEAD_IN, family
from test_multitrack import FAMILIES, SONGS, estimate

BEATS = Path(DATA, "structure", "beats")


def score_notes(song: str) -> dict[str, list[tuple[float, float, int]]]:
    """The score's notes (no jitter) by family, in mix time."""
    src = next(Path(DATA, f).joinpath(song, "song.mid") for f in ("score_songs", "score_songs_changes")
               if Path(DATA, f, song, "song.mid").exists())
    out: dict[str, list] = {}
    for inst in pretty_midi.PrettyMIDI(str(src)).instruments:
        out.setdefault(family(inst), []).extend((n.start + LEAD_IN, n.end + LEAD_IN, n.pitch) for n in inst.notes)
    return out


def gt_beats(song: str) -> np.ndarray:
    folder = next(f for f in ("score_songs", "score_songs_changes") if Path(DATA, f, song).exists())
    return np.array(json.loads(Path(DATA, folder, song, "ground_truth.json").read_text())["beats"])


def detected_grid(song: str, truth: np.ndarray, folder: Path = BEATS) -> tuple[np.ndarray, int] | None:
    """Detected beats and the score beat index of their first beat; None if the tempo is off."""
    path = folder / f"score__{song}.json"
    if not path.exists():
        return None
    beats = np.array(json.loads(path.read_text())["beats"])
    ratio = np.median(np.diff(beats)) / np.median(np.diff(truth))
    if not 0.8 < ratio < 1.25:
        return None
    return beats, int(round(float(notation.beat_position(np.array([beats[0]]), truth)[0])))


def evaluate_part(ref: list, est: list, truth_beats: np.ndarray, grid: np.ndarray, offset: int, mono: bool) -> tuple[int, int, int, int, int]:
    """(right in notation, matched, estimated notes, reference notes, right within the beat)."""
    if not ref or not est:
        return 0, 0, len(est), len(ref), 0
    r = np.array(ref, dtype=float)
    true_units = np.round(notation.beat_position(r[:, 0], truth_beats) * notation.UNIT).astype(int)
    q = notation.quantize(est, grid, monophonic=mono)
    # quantized notes back in seconds on the grid used, to match them with the score's notes
    est_on = np.array([np.interp(n.start / notation.UNIT, np.arange(len(grid)), grid) for n in q])
    e = np.array([(t, t + 0.1, n.pitch) for t, n in zip(est_on, q)], dtype=float)
    hz = mir_eval.util.midi_to_hz
    pairs = mir_eval.transcription.match_notes(r[:, :2], hz(r[:, 2]), e[:, :2], hz(e[:, 2]), onset_tolerance=0.07, offset_ratio=None)
    right = sum(q[j].start + offset * notation.UNIT == true_units[i] for i, j in pairs)
    # the rhythm figure: the same place within the beat, whatever the beat's number
    in_beat = sum(q[j].start % notation.UNIT == true_units[i] % notation.UNIT for i, j in pairs)
    return right, len(pairs), len(q), len(ref), in_beat


def main() -> None:
    songs = sorted(p.parent.name for p in SONGS.glob("*/notes.json"))
    inputs = {"true_notes": None, "ymt3_mix": "ymt3_mix", "bp_demucs": "bp_demucs"}
    result: dict[str, dict] = {}
    grids = {"detected_beats": BEATS, "app_beats": Path(DATA, "structure", "beats_app")}
    for grid_name in ("score_beats", "detected_beats", "app_beats"):
        for input_name, method in inputs.items():
            counts = {f: np.zeros(5, dtype=int) for f in FAMILIES}
            off_tempo = 0
            for song in songs:
                truth = gt_beats(song)
                if grid_name == "score_beats":
                    grid, offset = truth, 0
                else:
                    found = detected_grid(song, truth, grids[grid_name])
                    if found is None:
                        off_tempo += 1
                    grid, offset = found if found else (truth, None)
                ref = score_notes(song)
                if method is None:
                    played = json.loads((SONGS / song / "notes.json").read_text())
                    est = {f: [tuple(n[:3]) for n in v] for f, v in played.items()}
                else:
                    raw = estimate(method, song)
                    if raw is None:
                        continue
                    est = {f: [tuple(x) for x in v] for f, v in raw.items()}
                for fam in FAMILIES:
                    if fam not in ref:
                        continue
                    if offset is None:  # wrong tempo: nothing is right
                        counts[fam] += [0, 0, len(est.get(fam, [])), len(ref[fam]), 0]
                        continue
                    counts[fam] += evaluate_part(ref[fam], est.get(fam, []), truth, grid, offset, fam in ("bass", "lead"))
            row = {}
            for fam, (right, matched, n_est, n_ref, in_beat) in counts.items():
                p, r = right / max(n_est, 1), right / max(n_ref, 1)
                row[fam] = {"notation_f": round(2 * p * r / (p + r), 3) if right else 0.0,
                            "position_right_of_found": round(right / max(matched, 1), 3),
                            "rhythm_right_of_found": round(in_beat / max(matched, 1), 3)}
            if grid_name != "score_beats":
                row["songs_with_wrong_tempo"] = off_tempo
            result[f"{grid_name}/{input_name}"] = row
            print(grid_name, input_name, json.dumps(row))
    save_result("notation", result)


if __name__ == "__main__":
    main()
