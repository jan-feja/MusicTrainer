# Music Trainer

An app for practising music with songs. The idea and planned features are in [docs/use-cases.md](docs/use-cases.md) and [docs/functionalities.md](docs/functionalities.md).

**Current state:** a small YouTube client in the spirit of NewPipe, with practice loops that snap to the beat.

- **Search** YouTube, or paste a video link.
- **Download** videos into a local library: up to 720p H.264 + AAC MP4, with thumbnail and metadata. Progress is shown live.
- **Play** from the library:
  - speed 0.25–2× in steps of 0.05, keeping the pitch
  - an **A–B loop**: set A / B at the playhead, drag the handles on the timeline, nudge each point by 50 ms, turn it on or off. The jump back to A has no gap, at any speed
  - **beat-synced loops**:
    - beats and bar starts are detected automatically after each download; the bars of a section have the same number of beats, and the meter may change between sections (a verse in 3/4, a chorus in 4/4), as may the tempo
    - switch *Snap loop* to **Beats** or **Bars**, and A / B snap to the grid when set or dragged; the nudge buttons and ← → on a handle step one beat or bar
    - the loop length shows in beats or bars
    - fix the grid when the music is ambiguous (saved with the video):
      - **½× / 2×**: the tempo was detected an octave off (e.g. 150 instead of 75 BPM)
      - **beats per bar**: Auto (detected; e.g. *Auto (4, 3)* when sections differ), or 2-9 / 12 for the whole song
      - **‹ Bar start ›**: the bar starts are on the wrong beat from here on (e.g. after a 2/4 bar)
      - **Steady**: the song is played to a click, so all beats are spaced exactly evenly
    - the song's tempo is shown at the current speed
  - **saved loops**, kept with the video, as many as you like:
    - **+ Save loop** (S) keeps the current loop with its snap and speed; it gets a name (double-click to rename)
    - pick one (or press 1–9): its snap and speed are set, playback goes to its start and the timeline zooms to it
    - changing the picked loop (moving A / B, speed, snap) saves it; **New loop** starts another one
    - the timeline marks where the other saved loops are
  - **zoom** the timeline to adjust a loop precisely:
    - **−** / **+**, **Fit loop** (the loop fills the timeline), **Whole song**; Z switches between the loop and the whole song
    - Ctrl + scroll (or pinch) on the timeline zooms around the pointer, Shift + scroll moves
    - a strip under the zoomed timeline shows the whole song: drag its window or click to move
    - zoomed in, the bars are numbered and the beats marked; while playing, the view moves on with the playhead
  - **reopening a video** brings the player back as it was left: volume, speed, snap, the loop (zoomed to it) and the position
  - volume and full screen
  - keyboard shortcuts

Opening a video that isn't downloaded yet starts the download and plays it when done.

## Project structure

```
backend/        Python server: REST API, YouTube access, video library, beat detection (FastAPI + yt-dlp + Beat This!)
  src/music_trainer/
    api/          HTTP routes: /api/search, /api/library (incl. /beats, /audio), /api/downloads
    services/     youtube.py (search, download), library.py (videos on disk), downloads.py (background jobs),
                  beats.py + beat_analysis.py (beat detection and its background job),
                  beat_decoding.py (beat grid from the network output), audio.py (ffmpeg decoding)
    config.py     settings, read from MUSIC_TRAINER_* environment variables
    models.py     data models shared by services and API
  tests/          pytest; tests/integration use the real YouTube and beat model (opt-in)
frontend/       Browser UI (React + TypeScript + Vite)
  src/
    api/          typed client for the backend API
    app/          app shell: routes, header
    components/   shared UI pieces (video card, grid, progress bar, ...)
    features/     search/, library/, downloads/, player/ (player, A–B loop, gapless loop audio, speed, zoom),
                  beats/ (beat grid, snapping), practice/ (saved loops, player settings kept with the video)
    lib/          small helpers and hooks
docs/           planning documents, app survey, implementation report
experiments/    feasibility tests from the research phase (independent of the app)
data/           downloaded videos and model weights (created at runtime, not in git)
```

## Requirements

- **Python 3.11+**
- **Node.js 22+** (LTS)
- **ffmpeg** on `PATH`, to merge the video and audio streams
- **Deno**, recommended: yt-dlp needs a JavaScript runtime for YouTube. Install it with `winget install DenoLand.Deno`, or point `MUSIC_TRAINER_DENO_PATH` at `deno.exe`. Without it, some videos may fail to download.
- **Disk space for beat detection:**
  - PyTorch is installed with the backend: about 200 MB for the CPU build, which PyPI ships on Windows and macOS. On Linux, add `--extra-index-url https://download.pytorch.org/whl/cpu` to get it instead of the large CUDA build.
  - The first analysis downloads the 78 MB Beat This! model into `data/models/` and checks its checksum.

## Setup

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

cd ..\frontend
npm install
```

## Running

**Development** (auto-reload), in two terminals:

```powershell
# terminal 1: API on http://127.0.0.1:8000
cd backend
.venv\Scripts\uvicorn music_trainer.app:create_app --factory --reload

# terminal 2: UI on http://localhost:5173 (forwards /api to the backend)
cd frontend
npm run dev
```

**Single server**: build the UI once, and the backend serves it:

```powershell
cd frontend; npm run build
cd ..\backend; .venv\Scripts\music-trainer      # open http://127.0.0.1:8000
```

Interactive API documentation: http://127.0.0.1:8000/docs

## Tests and code checks

| | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| Unit tests | `.venv\Scripts\pytest` | `npm test` |
| Tests against real YouTube and the real beat model | `.venv\Scripts\pytest -m network` | – |
| Beat grid regression set: 226 songs decoded and compared with their true bars (~40 s; run before changing the decoder) | `.venv\Scripts\pytest -m beat_regression -s` | – |
| Lint | `.venv\Scripts\ruff check` | `npm run lint` |
| Format | `.venv\Scripts\ruff format` | `npm run format` |
| Type check | – | `npm run typecheck` |

## Configuration

Environment variables, or a `.env` file in the folder you start the backend from:

| Variable | Default | Meaning |
|---|---|---|
| `MUSIC_TRAINER_DATA_DIR` | `data/` in the repository | where the library is stored |
| `MUSIC_TRAINER_MAX_VIDEO_HEIGHT` | `720` | highest resolution to download |
| `MUSIC_TRAINER_MAX_PARALLEL_DOWNLOADS` | `2` | downloads that run at the same time |
| `MUSIC_TRAINER_DENO_PATH` | look up on `PATH` | Deno executable for yt-dlp |
| `MUSIC_TRAINER_FFMPEG_PATH` | look up on `PATH` | ffmpeg executable or folder |
| `MUSIC_TRAINER_HOST`, `MUSIC_TRAINER_PORT` | `127.0.0.1`, `8000` | server address |
| `MUSIC_TRAINER_FRONTEND_DIST_DIR` | `frontend/dist` | built UI to serve |
| `MUSIC_TRAINER_BEAT_MODEL` | `final0` | Beat This! model: `final0` (78 MB) or `small0` (8 MB, ~40 % faster); `final0,final1,final2` averages three models: loops right ~2 % more often on real music, 3× the time (best with a GPU) |
| `MUSIC_TRAINER_ANALYSIS_DEVICE` | `cpu` | `cuda` to run beat detection on an NVIDIA GPU |
| `MUSIC_TRAINER_ANALYZE_BEATS_AFTER_DOWNLOAD` | `true` | detect beats right after each download; otherwise when a video is first opened |

## How it works

- **Search:** yt-dlp reads YouTube's result list (`ytsearch`, without opening each video) and the API returns it as JSON.
- **Download:**
  1. A background thread asks yt-dlp for H.264 video + AAC audio (≤ 720p).
  2. ffmpeg merges them into one MP4.
  3. Everything is written to a staging folder first, then moved into the library when complete.

  The UI polls the progress every second while downloads run.
- **Beat detection** ([docs/beat-tracking.md](docs/beat-tracking.md)):
  1. After a download, a background job decodes the audio with ffmpeg.
  2. The [Beat This!](https://github.com/CPJKU/beat_this) network (ISMIR 2024, MIT) says, 50 times per second, how likely a beat and a bar start are: about 9 s for a 4-minute song on a laptop CPU. This output is stored as `beat_activations.npz`.
  3. A decoder (`beat_decoding.py`, a bar-pointer HMM in numpy) finds the most likely beat grid: the tempo changes only gradually and does not jump to its double or half, and within a section every bar has the same number of beats (3-8). The meter may change between sections of at least 4 bars. A few seconds.
  4. The grid is stored as `analysis.json` (BPM, beats per bar, beat and bar times, the user's hints).

  The player asks for it and polls while detection runs. New hints only decode again (seconds; moving bar starts is instant), the old grid stays on screen meanwhile. Grids of an older decoder are decoded again from the stored network output (keeping the hints) when the video is opened.

  Accuracy: see [docs/beat-tracking.md](docs/beat-tracking.md). Detected beats sit 10-20 ms after sharp attacks, so a loop snapped to the grid jumps 30 ms early and keeps the first note's attack.
- **Library on disk:** `data/library/<video-id>/` holds `meta.json`, `video.mp4`, `thumbnail.jpg`, `analysis.json`, `beat_activations.npz`, and once the video was played `loops.json` (saved loops) and `player.json` (how the player was left). Later features (stems) belong in the same folder; see [docs/functionalities.md](docs/functionalities.md).
- **Saved loops and settings:** the player loads them with the video (`GET /api/library/<id>/loops` and `/settings`) and stores changes a moment later (`PUT`, the whole list or settings at once; whatever is pending is sent when the page is left).
- **Player:** the browser's `<video>` element. Speed uses `playbackRate` with `preservesPitch`.
- **Gapless loops** (`frontend/src/features/player/gaplessLoop.ts`): seeking the `<video>` back to A silences it while the browser's media pipeline restarts, 5–190 ms per jump on the library songs. So the loop's sound comes from Web Audio instead:
  1. When A is set, the browser fetches the audio around it once (`GET /api/library/<id>/audio?start=&end=`, a WAV cut sample-exactly by ffmpeg, about 0.2 s for 40 s of audio).
  2. When the video reaches B, a [Signalsmith Stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch) node (MIT, WebAssembly in an AudioWorklet) takes over the sound, exactly at B. It loops the audio sample-exactly and keeps the pitch at any speed.
  3. The video plays on muted and is moved back to A at each pass; it may lag the sound by up to ~0.1 s right after the jump.
  4. Pausing, seeking out of the loop or turning it off gives the sound back to the video. Without Web Audio support, or if the audio cannot be fetched, the loop seeks back as before.

  Measured in Chrome on a 100 BPM metronome: the click spacing across the jump stays 600.0 ± 0.1 ms (before: 5–190 ms longer), and the first jump, where the stretcher takes over from the video, is 1–4 ms early. Per-instrument tracks ([docs/implementation-report.md](docs/implementation-report.md)) can later go through the same Web Audio path.

## Note

Downloading from YouTube is against YouTube's terms of service. This is a personal practice tool; don't publish it as a downloader.
