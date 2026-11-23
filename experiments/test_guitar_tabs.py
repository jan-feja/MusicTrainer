"""Recorded guitar -> notes -> tab: how much of a real guitarist's tab comes out right?

GuitarSet guitarist 05 (60 excerpts: comping and solos in five styles, microphone recording);
the hexaphonic pickup annotations give every note's pitch, time and string.
Caveat: Basic Pitch and YourMT3+ both saw parts of GuitarSet in training (YourMT3+ splits it by
random players per excerpt), so the note scores are optimistic; the string choice is not
learned by either (strings come from tablature.assign_frets, tuned on guitarists 00-04).

Methods: Basic Pitch (guitar range), YourMT3+ (every pitched note it finds).
Metrics (onset within 50 ms):
  note F    right pitch
  tab F     right pitch and right string (= right fret)
  string    share of the correctly found notes that are also on the right string

Usage:
  python yourmt3_runner.py MT_DATA/transcription/guitarset_ymt3 <05_*_mic.wav>   (venv of YourMT3+)
  python test_guitar_tabs.py                                                     (writes results/guitar_tabs.json)
"""

import json
from pathlib import Path

import mir_eval
import numpy as np

import tablature as tab
from common import DATA, save_result
from test_tablature import guitarset_notes

ROOT = Path(DATA, "guitarset")
WORK = Path(DATA, "transcription")
PLAYER = "05"


def excerpts() -> list[str]:
    return sorted(p.stem for p in (ROOT / "annotation").glob(f"{PLAYER}_*.jams"))


def basic_pitch(name: str) -> list[tuple[float, float, int]]:
    cache = WORK / "guitarset_bp" / f"{name}.json"
    if not cache.exists():
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict

        _, _, events = predict(str(ROOT / "audio_mono-mic" / f"{name}_mic.wav"), ICASSP_2022_MODEL_PATH,
                               minimum_frequency=70, maximum_frequency=1400)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps([(float(e[0]), float(e[1]), int(e[2])) for e in events]))
    return [tuple(n) for n in json.loads(cache.read_text())]


def yourmt3(name: str) -> list[tuple[float, float, int]] | None:
    import pretty_midi

    path = WORK / "guitarset_ymt3" / f"{name}_mic.mid"
    if not path.exists():
        return None
    return [(n.start, n.end, n.pitch) for inst in pretty_midi.PrettyMIDI(str(path)).instruments
            if not inst.is_drum for n in inst.notes]


def scores(truth: list[tuple[float, float, int, int]], est: list[tuple[float, float, int]]) -> dict:
    hz = mir_eval.util.midi_to_hz
    ref = np.array([t[:3] for t in truth], dtype=float)
    frets = tab.assign_frets(est)
    if not frets:
        return {"note": (0.0, 0.0, 0.0), "tab": (0.0, 0.0, 0.0), "matched": 0, "string_ok": 0}
    e = np.array([(n.onset, n.offset, n.pitch) for n in frets], dtype=float)
    pairs = mir_eval.transcription.match_notes(ref[:, :2], hz(ref[:, 2]), e[:, :2], hz(e[:, 2]),
                                               onset_tolerance=0.05, offset_ratio=None)
    string_ok = sum(truth[i][3] == frets[j].string for i, j in pairs)

    def prf(hits):
        p, r = hits / len(e), hits / len(ref)
        return p, r, 2 * p * r / (p + r) if hits else 0.0

    return {"note": prf(len(pairs)), "tab": prf(string_ok), "matched": len(pairs), "string_ok": string_ok}


def main() -> None:
    tuned = json.loads(Path(__file__).with_name("results").joinpath("tablature.json").read_text())["tuned_costs"]
    tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = tuned["move"], tuned["height"], tuned["open_bonus"]
    result = {}
    for method, fn in (("basic_pitch", basic_pitch), ("yourmt3", yourmt3), ("true_notes", None)):
        rows = []
        for name in excerpts():
            truth = guitarset_notes(ROOT / "annotation" / f"{name}.jams")
            est = [t[:3] for t in truth] if fn is None else fn(name)
            if est is None:
                continue
            rows.append(scores(truth, est))
        if not rows:
            continue
        result[method] = {
            "note_f": round(float(np.mean([r["note"][2] for r in rows])), 3),
            "note_p": round(float(np.mean([r["note"][0] for r in rows])), 3),
            "note_r": round(float(np.mean([r["note"][1] for r in rows])), 3),
            "tab_f": round(float(np.mean([r["tab"][2] for r in rows])), 3),
            "string_of_found": round(sum(r["string_ok"] for r in rows) / max(1, sum(r["matched"] for r in rows)), 3),
            "excerpts": len(rows),
        }
        print(method, result[method])
    save_result("guitar_tabs", result)


if __name__ == "__main__":
    main()
