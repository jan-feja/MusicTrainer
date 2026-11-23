"""Imported notation on real recordings: does it line up with the music after alignment?

Nine of the downloaded Harmonix songs have files in the Lakh MIDI Dataset (clean_midi, matched by
artist and title; several have 2-4 versions, all are tested). Fan-made MIDI files differ from the
record: other arrangement, sometimes other repeats, a steady tempo where the band drifts.

Methods (imported MIDI -> times in the recording):
  synctoolbox   chroma + onset features of the audio vs of the MIDI notes, multi-resolution DTW
                (Mueller et al.; the method test_alignment.py chose on synthetic songs)
  via_notes     the recording transcribed by YourMT3+ first, then notes vs notes with the same
                features (both sides symbolic: no timbre or mix in the way)
Answer: the Harmonix beat annotations (moved onto the YouTube audio as in structure_common;
songs whose annotations do not line up with the audio are left out). The MIDI's own beats,
mapped into the recording, should fall on annotated beats.

Variant "+beats": every mapped MIDI beat moved to the nearest Beat This! beat when one is within
150 ms (the app has that grid anyway).

Metrics: share of annotated beats with a mapped MIDI beat within 100 ms (beats the MIDI may have
at half or double tempo are fine one way: recall), median error, and the share of the song's
duration the alignment covers.

Usage: python test_import_alignment.py     (writes results/import_alignment.json; needs the
YourMT3+ transcriptions in MT_DATA/transcription/real_ymt3/<song>.mid for via_notes)
"""

import csv
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pretty_midi

import structure_common as sc
from common import DATA, save_result
from test_alignment import FR, align_synctoolbox

LAKH = Path(DATA, "lakh", "clean_midi")
META = Path(DATA, "harmonix_full", "harmonixset-main", "dataset", "metadata.csv")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def matches() -> list[tuple[str, list[Path]]]:
    artists = {norm(a): a for a in os.listdir(LAKH)}
    songs = {p.stem for p in Path(DATA, "songs").glob("*.wav")}
    out = []
    for row in csv.DictReader(open(META, encoding="utf8")):
        if row["File"] not in songs or norm(row["Artist"]) not in artists:
            continue
        folder = LAKH / artists[norm(row["Artist"])]
        files = sorted(f for f in folder.iterdir() if norm(f.stem).startswith(norm(row["Title"])[:12]))
        if files:
            out.append((row["File"], files))
    return out


def annotated_beats(song: str) -> np.ndarray | None:
    shift = sc.aligned_shift(song)
    if shift is None:
        return None
    rows = np.loadtxt(Path(DATA, "harmonix", "ann", f"{song}.beats_and_downbeats.txt"))
    beats = rows[:, 0] + shift
    # keep the song only if the moved annotations agree with Beat This! on the YouTube audio
    det = Path(DATA, "structure", "beats", f"harmonix__{song}.json")
    if det.exists():
        found = np.array(json.loads(det.read_text())["beats"])
        near = np.array([np.min(np.abs(found - b)) for b in beats])
        if np.mean(near < 0.07) < 0.6:
            return None
    return beats


def notes_df(pm: pretty_midi.PrettyMIDI) -> pd.DataFrame:
    rows = [dict(start=n.start, duration=n.end - n.start, pitch=n.pitch, velocity=n.velocity, instrument=inst.name or "x")
            for inst in pm.instruments if not inst.is_drum for n in inst.notes]
    return pd.DataFrame(rows)


def align_notes(transcription: Path, midi: Path):
    """Symbolic vs symbolic with synctoolbox's features and MrMsDTW."""
    from synctoolbox.dtw.mrmsdtw import sync_via_mrmsdtw
    from synctoolbox.dtw.utils import compute_optimal_chroma_shift, make_path_strictly_monotonic, shift_chroma_vectors
    from synctoolbox.feature.chroma import pitch_to_chroma, quantize_chroma, quantized_chroma_to_CENS
    from synctoolbox.feature.csv_tools import df_to_pitch_features, df_to_pitch_onset_features
    from synctoolbox.feature.dlnco import pitch_onset_features_to_DLNCO

    def feats(df):
        chroma = quantize_chroma(f_chroma=pitch_to_chroma(f_pitch=df_to_pitch_features(df, feature_rate=FR)))
        dlnco = pitch_onset_features_to_DLNCO(f_peaks=df_to_pitch_onset_features(df), feature_rate=FR,
                                              feature_sequence_length=chroma.shape[1], visualize=False)
        return chroma, dlnco

    ca, oa = feats(notes_df(pretty_midi.PrettyMIDI(str(transcription))))
    cs, os_ = feats(notes_df(pretty_midi.PrettyMIDI(str(midi))))
    shift = compute_optimal_chroma_shift(quantized_chroma_to_CENS(ca, 201, 50, FR)[0], quantized_chroma_to_CENS(cs, 201, 50, FR)[0])
    cs, os_ = shift_chroma_vectors(cs, shift), shift_chroma_vectors(os_, shift)
    wp = sync_via_mrmsdtw(f_chroma1=ca, f_onset1=oa, f_chroma2=cs, f_onset2=os_, input_feature_rate=FR,
                          step_weights=np.array([1.5, 1.5, 2.0]), threshold_rec=10**6, verbose=False)
    wp = make_path_strictly_monotonic(wp)
    return wp[0] / FR, wp[1] / FR


CACHE = Path(DATA, "transcription", "align_cache")


def cached(method: str, song: str, midi: Path, fn):
    path = CACHE / f"{method}__{song}__{norm(midi.stem)}.npz"
    if not path.exists():
        audio_t, score_t = fn()
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez(path, audio_t=audio_t, score_t=score_t)
    data = np.load(path)
    return data["audio_t"], data["score_t"]


def detected_beats(song: str) -> np.ndarray:
    return np.array(json.loads(Path(DATA, "structure", "beats", f"harmonix__{song}.json").read_text())["beats"])


def score(audio_t: np.ndarray, score_t: np.ndarray, midi: Path, truth: np.ndarray, snap: np.ndarray | None = None) -> dict:
    order = np.argsort(score_t)
    midi_beats = pretty_midi.PrettyMIDI(str(midi)).get_beats()
    midi_beats = midi_beats[(midi_beats >= score_t.min()) & (midi_beats <= score_t.max())]
    mapped = np.interp(midi_beats, score_t[order], audio_t[order])
    if snap is not None and len(snap) > 1:
        i = np.clip(np.searchsorted(snap, mapped), 1, len(snap) - 1)
        left, right = snap[i - 1], snap[i]
        nearest = np.where(np.abs(mapped - left) <= np.abs(right - mapped), left, right)
        mapped = np.where(np.abs(nearest - mapped) <= 0.15, nearest, mapped)
    inside = truth[(truth >= mapped.min()) & (truth <= mapped.max())] if len(mapped) else truth[:0]
    err = np.array([np.min(np.abs(mapped - t)) for t in inside]) if len(inside) else np.array([np.inf])
    return {"within_100ms": float(np.mean(err < 0.1)), "median_ms": float(np.median(err) * 1000),
            "coverage": float(len(inside) / max(len(truth), 1))}


def main() -> None:
    rows = {}
    for song, files in matches():
        truth = annotated_beats(song)
        if truth is None:
            print("skip (annotations do not line up with the audio):", song)
            continue
        wav = Path(DATA, "songs", f"{song}.wav")
        trans = Path(DATA, "transcription", "real_ymt3", f"{song}.mid")
        for midi in files:
            key = f"{song}/{midi.name}"
            row = {}
            grid = detected_beats(song)
            jobs = {"synctoolbox": lambda: align_synctoolbox(str(wav), str(midi))}
            if trans.exists():
                jobs["via_notes"] = lambda: align_notes(trans, midi)
            for method, fn in jobs.items():
                try:
                    path = cached(method, song, midi, fn)
                    row[method] = score(*path, midi, truth)
                    row[method + "+beats"] = score(*path, midi, truth, snap=grid)
                except Exception as e:  # broken MIDI files exist in Lakh
                    row[method] = {"error": f"{type(e).__name__}: {e}"[:200]}
            rows[key] = row
            print(key, json.dumps(row))
    summary = {}
    for method in ("synctoolbox", "synctoolbox+beats", "via_notes", "via_notes+beats"):
        ok = [r[method] for r in rows.values() if method in r and "error" not in r[method]]
        if ok:
            summary[method] = {"files": len(ok),
                               "within_100ms_mean": round(float(np.mean([r["within_100ms"] for r in ok])), 3),
                               "within_100ms_median": round(float(np.median([r["within_100ms"] for r in ok])), 3),
                               "files_over_80pct": sum(r["within_100ms"] >= 0.8 for r in ok)}
    print(json.dumps(summary, indent=1))
    save_result("import_alignment", {"summary": summary, "per_file": rows})


if __name__ == "__main__":
    main()
