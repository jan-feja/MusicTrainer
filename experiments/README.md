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
| `FLUIDSYNTH`, `SOUNDFONT` | for rendering the synthetic songs |

#### Data
1. `python make_synth_song.py %MT_DATA%`: 4 versions of a synthetic band song with exact answers (beats, chords, key, sections, notes, separate instrument tracks).
2. Real songs: 8 songs from the [Harmonix Set](https://github.com/urinieto/harmonixset) (human-annotated beats and sections), audio downloaded from YouTube with yt-dlp into `%MT_DATA%/songs/`, annotations into `%MT_DATA%/harmonix/`.
3. `python make_scores.py`: bass tab (.gp5) and MusicXML made from the synthetic song's MIDI.
4. MUSDB18 7-second previews download automatically (`musdb` package).

#### Scripts
| Script | Feature |
|---|---|
| [test_beats.py](test_beats.py) | BPM, beats, downbeats: librosa, Beat This!, madmom |
| [test_beats_followup.py](test_beats_followup.py) | Beat This! final0 vs small0, timing precision, loop accuracy (needs `CKPT_DIR`) |
| [test_separation.py](test_separation.py) | stem separation quality and speed: Demucs models |
| [test_stretch.py](test_stretch.py) | offline speed change / pitch shift in Python |
| [test_harmony.py](test_harmony.py) | key, chords, tuning |
| [test_alignment.py](test_alignment.py) | aligning notation (MIDI) with a recording |
| [test_transcription.py](test_transcription.py) | audio to notes: Basic Pitch, ADTOF (drums) |
| [test_scoring.py](test_scoring.py) | scoring a simulated user take |
| [test_sections.py](test_sections.py) | song section detection |
| [run_browser_tests.py](run_browser_tests.py) + [browser/](browser/) | real-time speed change, alphaTab notation, essentia.js analysis in headless Chromium |
