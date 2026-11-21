"""Align imported notation (MIDI) with a recording.

The "notation" is song.mid, written at a steady 100 BPM. The "recordings"
are renditions with drifting tempo (synth_live), 35 cents flat (detune)
and a semitone down (eb). We know where every beat really is, so we can
measure the alignment error.

Methods:
  librosa_dtw   chroma of the audio vs chroma of the MIDI + plain DTW
  synctoolbox   chroma + onset features, multi-resolution DTW (Mueller et al.)
  downbeats     map bar k of the notation to the k-th detected downbeat
                (Beat This!); assumes the bar counts match
"""
import warnings

import librosa
import numpy as np
import pandas as pd
import pretty_midi

from common import BEAT_THIS_CKPT, DEVICE, load_gt, save_result, synth_dir

warnings.filterwarnings("ignore")
FS = 22050
FR = 50  # feature rate (frames / s)


def score_notes(midi_path):
    pm = pretty_midi.PrettyMIDI(midi_path)
    rows = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            rows.append(dict(start=n.start, duration=n.end - n.start, pitch=n.pitch, velocity=n.velocity,
                             instrument=inst.name or "x"))
    return pm, pd.DataFrame(rows)


def align_librosa(audio_path, midi_path):
    y, _ = librosa.load(audio_path, sr=FS)
    hop = FS // FR
    ca = librosa.feature.chroma_cqt(y=y, sr=FS, hop_length=hop)
    ca = librosa.util.normalize(ca + 1e-6, axis=0)  # silent frames would give NaN distances
    pm, _ = score_notes(midi_path)
    for inst in pm.instruments:
        if inst.is_drum:
            inst.notes = []
    cs = pm.get_chroma(fs=FR)
    cs = librosa.util.normalize(cs + 1e-6, axis=0)
    # handle transposed recordings: try all 12 shifts on the averaged chroma
    shift = int(np.argmax([np.dot(np.roll(cs.mean(1), k), ca.mean(1)) for k in range(12)]))
    cs = np.roll(cs, shift, axis=0)
    _, wp = librosa.sequence.dtw(X=ca, Y=cs, metric="cosine")
    wp = wp[::-1]
    return wp[:, 0] / FR, wp[:, 1] / FR  # audio times, score times


def align_synctoolbox(audio_path, midi_path):
    from synctoolbox.dtw.mrmsdtw import sync_via_mrmsdtw
    from synctoolbox.dtw.utils import compute_optimal_chroma_shift, make_path_strictly_monotonic, shift_chroma_vectors
    from synctoolbox.feature.chroma import pitch_to_chroma, quantize_chroma, quantized_chroma_to_CENS
    from synctoolbox.feature.csv_tools import df_to_pitch_features, df_to_pitch_onset_features
    from synctoolbox.feature.dlnco import pitch_onset_features_to_DLNCO
    from synctoolbox.feature.pitch import audio_to_pitch_features
    from synctoolbox.feature.pitch_onset import audio_to_pitch_onset_features
    from synctoolbox.feature.utils import estimate_tuning

    y, _ = librosa.load(audio_path, sr=FS)
    tuning = estimate_tuning(y, FS)
    f_pitch = audio_to_pitch_features(f_audio=y, Fs=FS, tuning_offset=tuning, feature_rate=FR, verbose=False)
    f_chroma = quantize_chroma(f_chroma=pitch_to_chroma(f_pitch=f_pitch))
    f_onset = audio_to_pitch_onset_features(f_audio=y, Fs=FS, tuning_offset=tuning, verbose=False)
    f_dlnco = pitch_onset_features_to_DLNCO(f_peaks=f_onset, feature_rate=FR,
                                            feature_sequence_length=f_chroma.shape[1], visualize=False)
    _, df = score_notes(midi_path)
    f_pitch_s = df_to_pitch_features(df, feature_rate=FR)
    f_chroma_s = quantize_chroma(f_chroma=pitch_to_chroma(f_pitch=f_pitch_s))
    f_onset_s = df_to_pitch_onset_features(df)
    f_dlnco_s = pitch_onset_features_to_DLNCO(f_peaks=f_onset_s, feature_rate=FR,
                                              feature_sequence_length=f_chroma_s.shape[1], visualize=False)
    shift = compute_optimal_chroma_shift(quantized_chroma_to_CENS(f_chroma, 201, 50, FR)[0],
                                         quantized_chroma_to_CENS(f_chroma_s, 201, 50, FR)[0])
    f_chroma_s = shift_chroma_vectors(f_chroma_s, shift)
    f_dlnco_s = shift_chroma_vectors(f_dlnco_s, shift)
    wp = sync_via_mrmsdtw(f_chroma1=f_chroma, f_onset1=f_dlnco, f_chroma2=f_chroma_s, f_onset2=f_dlnco_s,
                          input_feature_rate=FR, step_weights=np.array([1.5, 1.5, 2.0]),
                          threshold_rec=10 ** 6, verbose=False)
    wp = make_path_strictly_monotonic(wp)
    return wp[0] / FR, wp[1] / FR


def align_downbeats(audio_path, midi_path):
    from beat_this.inference import File2Beats
    _, downbeats = File2Beats(checkpoint_path=BEAT_THIS_CKPT, device=DEVICE, dbn=False)(audio_path)
    score_bars = 0.5 + np.arange(len(downbeats)) * 2.4  # bar k of the notation (100 BPM, 4/4)
    return np.asarray(downbeats), score_bars


METHODS = {"librosa_dtw": align_librosa, "synctoolbox": align_synctoolbox, "downbeats": align_downbeats}


def main():
    midi = f"{synth_dir('steady')}/song.mid"
    score_beats = np.array(load_gt("steady")["beats"])
    res = {}
    for v in ("live", "detune", "eb"):
        true_beats = np.array(load_gt(v)["beats"])
        for name, fn in METHODS.items():
            try:
                a_t, s_t = fn(f"{synth_dir(v)}/mix.wav", midi)
                order = np.argsort(s_t)
                est = np.interp(score_beats, s_t[order], a_t[order])
                err = np.abs(est - true_beats) * 1000
                r = dict(mean_ms=float(err.mean()), median_ms=float(np.median(err)), p95_ms=float(np.percentile(err, 95)),
                         within_50ms=float(np.mean(err < 50)), within_100ms=float(np.mean(err < 100)))
            except Exception as e:
                r = {"error": f"{type(e).__name__}: {e}"}
            res[f"{v}/{name}"] = r
            print(f"{v:7s} {name:12s} " + (" ".join(f"{k}={val:.3f}" for k, val in r.items()) if "error" not in r else r["error"]))
    save_result("alignment", res)


if __name__ == "__main__":
    main()
