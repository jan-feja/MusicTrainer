### Experiments
Scripts behind [../docs/implementation-report.md](../docs/implementation-report.md). Each one tests one feature and writes its numbers to [results/](results/).

#### Setup (Windows, Python 3.11)
```
py -3.11 -m venv venv
venv\Scripts\pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
venv\Scripts\pip install numpy==1.26.4 librosa mir_eval pretty_midi soundfile pedalboard demucs musdb music21 pyguitarpro Cython synctoolbox "basic-pitch[onnx]"
venv\Scripts\pip install https://github.com/CPJKU/beat_this/archive/main.zip
venv\Scripts\pip install --no-build-isolation git+https://github.com/CPJKU/madmom   # needs Visual C++ build tools
git clone https://github.com/xavriley/ADTOF-pytorch && venv\Scripts\pip install --no-deps -e ADTOF-pytorch
```
Browser tests use a second venv with `pip install playwright numpy soundfile` and `python -m playwright install chromium`.

Tools (portable, no install): [yt-dlp.exe](https://github.com/yt-dlp/yt-dlp/releases), [Deno](https://github.com/denoland/deno/releases) (yt-dlp needs it for YouTube), [FluidSynth](https://github.com/FluidSynth/fluidsynth/releases) + [GeneralUser GS](https://github.com/mrbumpy409/GeneralUser-GS) SoundFont, ffmpeg.

#### Environment variables
| Variable | Meaning |
|---|---|
| `MT_DATA` | data folder (songs, synthetic songs, models; not in git) |
| `MT_DEVICE` | `cuda` or `cpu` |
| `BEAT_THIS_CKPT` | path to Beat This! weights (the official download server was rate-limiting; see the report) |
| `CKPT_DIR` | folder with Beat This! checkpoints as `<name>.ckpt` (`final0`, `final1`, `final2`, `small0`) for the beat tracking scripts |
| `MT_LIBRARY` | the app's `data/library`, for checks on downloaded songs (default: the repository's) |
| `FLUIDSYNTH`, `SOUNDFONT` | for rendering the synthetic songs |

#### Data
1. `python make_synth_song.py %MT_DATA%`: 4 versions of a synthetic band song with exact answers (beats, chords, key, sections, notes, separate instrument tracks).
2. Real songs: 8 songs from the [Harmonix Set](https://github.com/urinieto/harmonixset) (human-annotated beats and sections), audio downloaded from YouTube with yt-dlp into `%MT_DATA%/songs/`, annotations into `%MT_DATA%/harmonix/`.
3. `python make_scores.py`: bass tab (.gp5) and MusicXML made from the synthetic song's MIDI.
4. MUSDB18 7-second previews download automatically (`musdb` package).
5. Score songs for beat tracking (exact answers, music no model was trained on):
   ```
   python make_score_songs.py %MT_DATA%/score_midi 3        # 17 songs x 3 tempo variants, as MIDI
   python score_to_audio.py %MT_DATA%/score_songs %MT_DATA%/score_midi  [more .mid / .gp5 files or folders]
   ```
   `score_to_audio.py` also takes Guitar Pro 3/4/5 tabs and any MIDI file: drop a tab of a song into the list and it becomes a test song.
6. GTZAN (real music, held out from Beat This! training): audio `genres.tar.gz` from the Hugging Face dataset `marsyas/gtzan`, unpacked to `%MT_DATA%/gtzan/genres/`; annotations from [CPJKU/beat_this_annotations](https://github.com/CPJKU/beat_this_annotations) unpacked to `%MT_DATA%/gtzan/beat_this_annotations-main/`.
7. Songs whose meter or tempo changes:
   ```
   python make_score_songs.py %MT_DATA%/score_midi_changes 3 --set changes      # 11 songs x 3 tempo variants
   python score_to_audio.py %MT_DATA%/score_songs_changes %MT_DATA%/score_midi_changes
   python get_harmonix_changes.py <harmonixset>/dataset    # needs yt-dlp + Deno and ffmpeg on PATH
   ```
   The score songs have verses in 3/4, 5/4, 6/4, 7/4 or 7/8 against a 4/4 chorus, a 4+4+4+3 bar cycle, a verse like Tool's *Pneuma* (6+6+5+6+5+5 eighths), tempo jumps, accelerando, ritardando and rubato. `get_harmonix_changes.py` picks the Harmonix songs whose annotations show meter changes (10 %+ of the bars of another length) or tempo changes, from a clone of [the Harmonix repository](https://github.com/urinieto/harmonixset), and downloads their YouTube audio (42 of 50; the other videos are gone).
   Many YouTube versions are other edits (longer intros, cut verses), so the annotations are moved onto them by DTW against the mel spectrograms the Harmonix authors publish: [Harmonix_melspecs.tgz](https://www.dropbox.com/s/zxnqlx0hxz0lsyc/Harmonix_melspecs.tgz?dl=0) (1.2 GB), unpacked to `%MT_DATA%/harmonix_melspecs/melspecs/` (`common.harmonix_warped`). Songs where neither that nor a constant shift lines the annotated beats up with the network's beats are left out (30 kept).
8. `python make_beat_regression_set.py`: writes the backend's regression set (`backend/tests/data/beat_grids/`, see its README) from the sets above.

#### Scripts
| Script | Feature |
|---|---|
| [test_beats.py](test_beats.py) | BPM, beats, downbeats: librosa, Beat This!, madmom |
| [test_beats_followup.py](test_beats_followup.py) | Beat This! final0 vs small0, timing precision, loop accuracy (needs `CKPT_DIR`) |
| [make_score_songs.py](make_score_songs.py), [score_to_audio.py](score_to_audio.py) | beat tracking test songs written as scores, rendered with exact answers |
| [test_beat_tracking.py](test_beat_tracking.py) | beat grid decoding: the app's decoder vs peak picking vs madmom's DBN on score songs, GTZAN, Harmonix and library songs, and on songs whose meter or tempo changes (sets `score_changes`, `harmonix_changes`) ([../docs/beat-tracking.md](../docs/beat-tracking.md)) |
| [get_harmonix_changes.py](get_harmonix_changes.py) | Harmonix songs with meter or tempo changes: selection, download, annotations |
| [make_beat_regression_set.py](make_beat_regression_set.py) | the backend's beat grid regression set (network outputs + true beats and bars of 226 songs) |
| [test_meter_sections.py](test_meter_sections.py) | decoder variants for meter and tempo changes (meter sections, tempo octave limit, single odd bars) on the regression set |
| [test_separation.py](test_separation.py) | stem separation quality and speed: Demucs models |
| [test_stretch.py](test_stretch.py) | offline speed change / pitch shift in Python |
| [test_harmony.py](test_harmony.py) | key, chords, tuning |
| [test_alignment.py](test_alignment.py) | aligning notation (MIDI) with a recording |
| [test_transcription.py](test_transcription.py) | audio to notes: Basic Pitch, ADTOF (drums) |
| [test_scoring.py](test_scoring.py) | scoring a simulated user take |
| [test_sections.py](test_sections.py) | song section detection |
| [run_browser_tests.py](run_browser_tests.py) + [browser/](browser/) | real-time speed change, alphaTab notation, essentia.js analysis in headless Chromium |
| [test_gapless_loop.py](test_gapless_loop.py) | gapless loops in the running app: click spacing of a metronome across the loop jump, at 1× and 0.75× (system Chrome; intervals short by multiples of 2.7 ms are audio blocks Chrome skipped under CPU load, they show up before the loop too) |
