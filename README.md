# Music Trainer

An app for practising music with songs. The idea and planned features are in [docs/use-cases.md](docs/use-cases.md) and [docs/functionalities.md](docs/functionalities.md).

**Current state:** a small YouTube client in the spirit of NewPipe, with practice loops that snap to the beat.

- **Search** YouTube, or paste a video link.
- **Download** videos into a local library: up to 720p H.264 + AAC MP4, with thumbnail and metadata. Progress is shown live.
- **Play** from the library:
  - speed 0.25–2× in steps of 0.05, keeping the pitch
  - an **A–B loop**: set A / B at the playhead, drag the handles on the timeline, nudge each point by 50 ms, turn it on or off
  - **beat-synced loops**:
    - beats and bar starts are detected automatically after each download
    - switch *Snap loop* to **Beats** or **Bars**, and A / B snap to the grid when set or dragged; the nudge buttons and ← → on a handle step one beat or bar
    - the loop length shows in beats or bars
    - if the bar start is on the wrong beat, move it with ‹ ›
    - the song's tempo is shown at the current speed
  - volume and full screen
  - keyboard shortcuts

Opening a video that isn't downloaded yet starts the download and plays it when done.

## Project structure

```
backend/        Python server: REST API, YouTube access, video library, beat detection (FastAPI + yt-dlp + Beat This!)
  src/music_trainer/
    api/          HTTP routes: /api/search, /api/library (incl. /beats), /api/downloads
    services/     youtube.py (search, download), library.py (videos on disk), downloads.py (background jobs),
                  beats.py + beat_analysis.py (beat detection and its background job), audio.py (ffmpeg decoding)
    config.py     settings, read from MUSIC_TRAINER_* environment variables
    models.py     data models shared by services and API
  tests/          pytest; tests/integration use the real YouTube and beat model (opt-in)
frontend/       Browser UI (React + TypeScript + Vite)
  src/
    api/          typed client for the backend API
    app/          app shell: routes, header
    components/   shared UI pieces (video card, grid, progress bar, ...)
    features/     search/, library/, downloads/, player/ (player, A–B loop, speed), beats/ (beat grid, snapping)
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
| `MUSIC_TRAINER_BEAT_MODEL` | `final0` | Beat This! model: `final0` (78 MB, most accurate) or `small0` (8 MB, ~40 % faster) |
| `MUSIC_TRAINER_ANALYSIS_DEVICE` | `cpu` | `cuda` to run beat detection on an NVIDIA GPU |
| `MUSIC_TRAINER_ANALYZE_BEATS_AFTER_DOWNLOAD` | `true` | detect beats right after each download; otherwise when a video is first opened |

## How it works

- **Search:** yt-dlp reads YouTube's result list (`ytsearch`, without opening each video) and the API returns it as JSON.
- **Download:**
  1. A background thread asks yt-dlp for H.264 video + AAC audio (≤ 720p).
  2. ffmpeg merges them into one MP4.
  3. Everything is written to a staging folder first, then moved into the library when complete.

  The UI polls the progress every second while downloads run.
- **Beat detection:**
  1. After a download, a background job decodes the audio with ffmpeg.
  2. [Beat This!](https://github.com/CPJKU/beat_this) (ISMIR 2024, MIT) finds the beats and bar starts: about 9 s for a 4-minute song on a laptop CPU.
  3. The result is stored as `analysis.json` (BPM, beats per bar, beat and bar times).

  The player asks for it and polls while detection runs; a video downloaded before this feature is analysed when first opened.

  Accuracy, measured in [experiments/test_beats_followup.py](experiments/test_beats_followup.py) on real songs: both ends of a 1–4 bar loop land on the right bar lines about 87 % of the time. The misses are mostly in soft intros without drums.

  Detected beats sit about 20 ms after sharp attacks, so a loop snapped to the grid jumps 30 ms early and keeps the first note's attack.
- **Library on disk:** `data/library/<video-id>/` holds `meta.json`, `video.mp4`, `thumbnail.jpg` and `analysis.json`. Later features (stems, `loops.json`) belong in the same folder; see [docs/functionalities.md](docs/functionalities.md).
- **Player:** the browser's `<video>` element. Speed uses `playbackRate` with `preservesPitch`. The loop end is checked on every animation frame (about every 16 ms). Jumping back to A seeks the video; in Chrome that took about 9 ms per jump. The audio engine planned in [docs/implementation-report.md](docs/implementation-report.md) (Web Audio + Signalsmith Stretch) would make loops gapless and add per-instrument tracks.

## Note

Downloading from YouTube is against YouTube's terms of service. This is a personal practice tool; don't publish it as a downloader.
