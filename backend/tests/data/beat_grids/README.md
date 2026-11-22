# Beat grid regression set

Test data for `tests/test_beat_regression.py` (`pytest -m beat_regression -s`). For every song: what the Beat This! network (final0) outputs for it, 50 times per second, and where its beats and bars really are. The decoder (`beat_decoding.py`) is run on the stored network output, so the test needs neither audio nor the network, and every decoder change shows song by song whether it helps or hurts.

| File | Contents |
|---|---|
| `songs.npz` | per song `<id>/beat` and `<id>/downbeat`: network logits as int8 steps of 0.25; `<id>/beats` and `<id>/downbeats`: true beat and bar-start times in seconds (not for library songs) |
| `manifest.json` | per song: id, group, category, source, title; for library songs the checks |
| `baseline.json` | the decoder's results per song when the baseline was last accepted |

## Songs (226)

| Group | Songs | What |
|---|---|---|
| `steady` | 146 | one meter, a steady tempo: 39 score songs (rock, ballad with half- and double-time, metal, 3/4, 6/8, 12/8, 5/4, 7/4, funk, swing, reggae, no drums, stops), 8 Harmonix songs, 99 GTZAN clips (10 per genre) |
| `tempo` | 27 | one meter, the tempo changes: score songs with tempo jumps, accelerando, ritardando, rubato and a drifting live tempo; 9 Harmonix songs (*Baba O'Riley*, *Good Mourning / Black Friday*, *Devil's Island*, ...) |
| `meter` | 50 | bars of different lengths: score songs with single odd bars, verses in 3/4, 5/4, 6/4, 7/4 or 7/8 against a 4/4 chorus, a 4+4+4+3 cycle and a verse like Tool's *Pneuma* (6+6+5+6+5+5 eighths); 22 Harmonix songs (Soundgarden *The Day I Tried to Live*, Killswitch Engage *My Curse*, Metallica *Blackened*, Rush *Tom Sawyer*, ...); 1 GTZAN clip |
| `library` | 3 | songs from the app library without annotations (*Cryin'*, *Charlie*, *Send Me On My Way*): only checks: beats per bar, tempo and, for songs in one steady tempo, that no stretch is decoded at double or half tempo |

Sources of the answers:
- **Score songs:** written as scores ([experiments/make_score_songs.py](../../../../experiments/make_score_songs.py), `--set changes` for the meter and tempo changes), rendered with FluidSynth ([score_to_audio.py](../../../../experiments/score_to_audio.py)): exact.
- **Harmonix Set** ([github.com/urinieto/harmonixset](https://github.com/urinieto/harmonixset), MIT): human annotations. The audio is the YouTube version, aligned with the annotated recording: the 8 steady songs by a constant shift, the others by DTW on the mel spectrograms the Harmonix authors publish ([experiments/common.py](../../../../experiments/common.py) `harmonix_offset`, `harmonix_warped`). Songs whose YouTube audio did not line up were left out. Beat This! was trained on the Harmonix Set, so the network does better on these than on new songs; the decoding is what is tested.
- **GTZAN:** annotations from [CPJKU/beat_this_annotations](https://github.com/CPJKU/beat_this_annotations); GTZAN was not in Beat This!'s training data.

Only network outputs and annotation times are stored here, no audio.

## Rules

- Per group, the mean beat and bar-start F-measure and the 1- and 4-bar loop accuracy must not drop more than 0.005 below the baseline.
- A song whose bar starts were right (F ≥ 0.9) must stay within 0.05 of its baseline.
- Library songs must keep their beats per bar and tempo.

The test prints the group means (baseline → now) and every song whose bar F-measure moved by 0.05 or more.

## Updating

- **The decoder improved:** run `UPDATE_BEAT_BASELINE=1 pytest -m beat_regression -s` (PowerShell: `$env:UPDATE_BEAT_BASELINE=1` first) to accept the new results. The run prints the old baseline next to the new one.
- **New songs:** add them to the experiment data and run `python make_beat_regression_set.py` in `experiments/` (needs `MT_DATA` with the test sets and cached network outputs; see [experiments/README.md](../../../../experiments/README.md)); then update the baseline.
