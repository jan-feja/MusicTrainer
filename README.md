# Music Trainer

An app for practising music with songs. The idea and planned features are in [docs/use-cases.md](docs/use-cases.md) and [docs/functionalities.md](docs/functionalities.md).

**Current state: the backbone.** A small YouTube client in the spirit of NewPipe:

- **Search** YouTube, or paste a video link.
- **Download** videos into a local library: up to 720p H.264 + AAC MP4, with thumbnail and metadata. Progress is shown live.
- **Play** from the library:
  - speed 0.25–2× in steps of 0.05, keeping the pitch
  - an **A–B loop**: set A / B at the playhead, drag the handles on the timeline, nudge each point by 50 ms, turn it on or off
  - volume and full screen
  - keyboard shortcuts

Opening a video that isn't downloaded yet starts the download and plays it when done.

## Project structure

```
backend/        Python server: REST API, YouTube access, video library (FastAPI + yt-dlp)
  src/music_trainer/
    api/          HTTP routes: /api/search, /api/library, /api/downloads
    services/     youtube.py (search, download), library.py (videos on disk), downloads.py (background jobs)
    config.py     settings, read from MUSIC_TRAINER_* environment variables
    models.py     data models shared by services and API
  tests/          pytest; tests/integration talk to the real YouTube (opt-in)
frontend/       Browser UI (React + TypeScript + Vite)
  src/
    api/          typed client for the backend API
    app/          app shell: routes, header
    components/   shared UI pieces (video card, grid, progress bar, ...)
    features/     search/, library/, downloads/, player/ (player, A–B loop and speed logic)
    lib/          small helpers and hooks
docs/           planning documents, app survey, implementation report
experiments/    feasibility tests from the research phase (independent of the app)
data/           downloaded videos (created at runtime, not in git)
```

## Requirements

- **Python 3.11+**
- **Node.js 22+** (LTS)
- **ffmpeg** on `PATH`, to merge the video and audio streams
- **Deno**, recommended: yt-dlp needs a JavaScript runtime for YouTube. Install it with `winget install DenoLand.Deno`, or point `MUSIC_TRAINER_DENO_PATH` at `deno.exe`. Without it, some videos may fail to download.

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
| Tests against real YouTube | `.venv\Scripts\pytest -m network` | – |
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

## How it works

- **Search:** yt-dlp reads YouTube's result list (`ytsearch`, without opening each video) and the API returns it as JSON.
- **Download:**
  1. A background thread asks yt-dlp for H.264 video + AAC audio (≤ 720p).
  2. ffmpeg merges them into one MP4.
  3. Everything is written to a staging folder first, then moved into the library when complete.

  The UI polls the progress every second while downloads run.
- **Library on disk:** `data/library/<video-id>/` holds `meta.json`, `video.mp4` and `thumbnail.jpg`. Later features (stems, `analysis.json`, `loops.json`) belong in the same folder; see [docs/functionalities.md](docs/functionalities.md).
- **Player:** the browser's `<video>` element. Speed uses `playbackRate` with `preservesPitch`. The loop end is checked on every animation frame (about every 16 ms). Jumping back to A seeks the video, so there's a very short gap. The audio engine planned in [docs/implementation-report.md](docs/implementation-report.md) (Web Audio + Signalsmith Stretch) would make loops gapless and add per-instrument tracks.

## Note

Downloading from YouTube is against YouTube's terms of service. This is a personal practice tool; don't publish it as a downloader.
