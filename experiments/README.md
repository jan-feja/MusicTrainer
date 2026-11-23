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

Transcription and sections ([../docs/transcription-and-sections.md](../docs/transcription-and-sections.md)) need three more environments:
- **YourMT3+** (Windows venv `venv_tx`): `torch==2.5.1` (cu121), `transformers==4.45.1`, `lightning`, `wandb`, `deprecated`, `mido`, `einops`, `librosa`, `mir_eval`, `pretty_midi`, plus `bs-roformer-infer` (git) for BS-RoFormer. The model code and checkpoint come from the Hugging Face Space `mimbres/YourMT3` (`amt/src`, `amt/logs/2024/mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/`); set `YOURMT3_DIR` to it.
- **SongFormer** (WSL, Python 3.10): clone [aslp-lab/songformer](https://github.com/aslp-lab/songformer) with submodules, `pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu121`, then its requirements (without gradio, wandb, modelscope, pesq, tensorboard), `python utils/fetch_pretrained.py` in `src/SongFormer`, and `python songformer_patch.py <checkout>` from here (6 GB GPU: flash attention + bfloat16; keeps the frame outputs).
- **All-In-One** (WSL): `torch==2.4.0` (cu121), NATTEN 0.17.5 built from source (CPU only; its wheel server's certificate had expired), madmom from git, `allin1`. Two patches: in `natten/functional.py` make the `.flex` import optional (needs torch 2.5), and in `allin1/models/dinat.py` map `natten1dqkrpb` / `natten1dav` / `natten2dqkrpb` / `natten2dav` to `na1d_qk` / `na1d_av` / `na2d_qk` / `na2d_av` (same tensor layout). The structure model then runs on the CPU, Demucs on the GPU.

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
7. Transcription and sections:
   - `python render_score_stems.py`: the score songs again, with every instrument's stem and exact notes (`MT_DATA/score_stems/`).
   - [SALAMI](https://github.com/DDMAL/salami-data-public) annotations cloned into `MT_DATA/salami/`; audio of its Internet Archive part: `python get_salami.py %MT_DATA%/salami 150` (147 usable).
   - [GuitarSet](https://guitarset.weebly.com/) annotations and mono microphone audio (`MT_DATA/guitarset/`); [IDMT-SMT-Guitar](https://zenodo.org/records/7544110) (`MT_DATA/idmt/`).
   - [GTZAN key annotations](https://github.com/alexanderlerch/gtzan_key) (`MT_DATA/gtzan_key/`); [Lakh MIDI clean_midi](https://colinraffel.com/projects/lmd/) (`MT_DATA/lakh/`).
   - Section test manifest: `python -c "import structure_common as s; s.write_manifest()"`.

#### Scripts
| Script | Feature |
|---|---|
| [test_beats.py](test_beats.py) | BPM, beats, downbeats: librosa, Beat This!, madmom |
| [test_beats_followup.py](test_beats_followup.py) | Beat This! final0 vs small0, timing precision, loop accuracy (needs `CKPT_DIR`) |
| [make_score_songs.py](make_score_songs.py), [score_to_audio.py](score_to_audio.py) | beat tracking test songs written as scores, rendered with exact answers |
| [test_beat_tracking.py](test_beat_tracking.py) | beat grid decoding: the app's decoder vs peak picking vs madmom's DBN on score songs, GTZAN, Harmonix and library songs ([../docs/beat-tracking.md](../docs/beat-tracking.md)) |
| [test_separation.py](test_separation.py) | stem separation quality and speed: Demucs models |
| [test_stretch.py](test_stretch.py) | offline speed change / pitch shift in Python |
| [test_harmony.py](test_harmony.py) | key, chords, tuning |
| [test_alignment.py](test_alignment.py) | aligning notation (MIDI) with a recording |
| [test_transcription.py](test_transcription.py) | audio to notes: Basic Pitch, ADTOF (drums) |
| [test_scoring.py](test_scoring.py) | scoring a simulated user take |
| [test_sections.py](test_sections.py) | song section detection (first version) |
| [structure_common.py](structure_common.py), [test_structure.py](test_structure.py) | song sections on SALAMI / Harmonix / score songs: SongFormer, All-In-One, Laplacian, bar decoding, human agreement |
| [songformer_patch.py](songformer_patch.py) | makes SongFormer run on a 6 GB GPU and keep its frame outputs |
| [render_score_stems.py](render_score_stems.py), [test_multitrack.py](test_multitrack.py), [yourmt3_runner.py](yourmt3_runner.py) | notes per instrument: YourMT3+, Demucs / BS-RoFormer + Basic Pitch + ADTOF, hybrids |
| [test_real_transcription.py](test_real_transcription.py) | transcription of real songs against aligned Lakh MIDI files |
| [tablature.py](tablature.py), [test_tablature.py](test_tablature.py), [test_guitar_tabs.py](test_guitar_tabs.py), [test_string_model.py](test_string_model.py) | strings and frets: fingering search, audio to tab on GuitarSet, a network that hears the string (also on IDMT electric guitars) |
| [notation.py](notation.py), [test_notation.py](test_notation.py), [transcribe_song.py](transcribe_song.py), [render_notation.py](render_notation.py) | notes to notation: beat-grid quantization, Guitar Pro 5, alphaTab screenshots |
| [test_chords.py](test_chords.py), [test_key.py](test_key.py), [test_tuning.py](test_tuning.py) | chords on real guitar recordings, key on GTZAN, tuning of real recordings |
| [test_import_alignment.py](test_import_alignment.py) | imported MIDI aligned to real recordings |
| [run_browser_tests.py](run_browser_tests.py) + [browser/](browser/) | real-time speed change, alphaTab notation, essentia.js analysis in headless Chromium |
| [test_gapless_loop.py](test_gapless_loop.py) | gapless loops in the running app: click spacing of a metronome across the loop jump, at 1× and 0.75× (system Chrome; intervals short by multiples of 2.7 ms are audio blocks Chrome skipped under CPU load, they show up before the loop too) |
