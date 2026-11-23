"""Strings and frets: how often does a fingering method pick the guitarist's string?

GuitarSet (360 excerpts, 6 guitarists, comping and solos, hexaphonic pickup annotations) gives
every note with the string it was played on. Given the true notes, each method assigns strings
and frets; the score is the share of notes on the right string (= right fret).

The fingering search's costs are tuned on guitarists 00-04 and reported on guitarist 05.
Usage: python test_tablature.py
"""

import itertools
import json
from pathlib import Path

import numpy as np

import tablature as tab
from common import DATA, save_result

ROOT = Path(DATA, "guitarset")


def guitarset_notes(jams_path: Path) -> list[tuple[float, float, int, int]]:
    """(onset, offset, midi pitch, string) of every annotated note."""
    data = json.loads(jams_path.read_text())
    notes = []
    for a in data["annotations"]:
        if a["namespace"] == "note_midi":
            string = int(a["annotation_metadata"]["data_source"])
            for n in a["data"]:
                notes.append((n["time"], n["time"] + n["duration"], int(round(n["value"])), string))
    return sorted(notes)


def string_accuracy(method, excerpts) -> float:
    right = total = 0
    for notes in excerpts:
        plain = [(a, b, p) for a, b, p, _ in notes]
        truth = {(round(a, 4), p): s for a, _, p, s in notes}
        for n in method(plain):
            total += 1
            right += truth.get((round(n.onset, 4), n.pitch)) == n.string
    return right / max(total, 1)


def main() -> None:
    files = sorted((ROOT / "annotation").glob("*.jams"))
    by_player = {}
    for f in files:
        by_player.setdefault(f.name[:2], []).append(guitarset_notes(f))
    train = [n for p, ex in by_player.items() if p != "05" for n in ex]
    test = by_player["05"]
    # tune the search's main costs on guitarists 00-04
    best = None
    for move, height, open_bonus in itertools.product((0.3, 0.6, 1.0, 1.5), (0.05, 0.15, 0.3), (0.0, 0.4, 0.8)):
        tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = move, height, open_bonus
        acc = string_accuracy(tab.assign_frets, train)
        if best is None or acc > best[0]:
            best = (acc, move, height, open_bonus)
    _, tab.MOVE_COST, tab.HEIGHT_COST, tab.OPEN_BONUS = best
    result = {
        "tuned_costs": {"move": tab.MOVE_COST, "height": tab.HEIGHT_COST, "open_bonus": tab.OPEN_BONUS},
        "train_00-04": {"search": round(best[0], 3), "lowest_fret": round(string_accuracy(tab.lowest_fret, train), 3)},
        "test_05": {"search": round(string_accuracy(tab.assign_frets, test), 3),
                    "lowest_fret": round(string_accuracy(tab.lowest_fret, test), 3)},
        "notes": {"train": sum(len(n) for n in train), "test": sum(len(n) for n in test)},
    }
    print(json.dumps(result, indent=1))
    save_result("tablature", result)


if __name__ == "__main__":
    main()
