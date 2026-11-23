# Music Trainer: Developer Guide

This guide describes the application on `main`. For player instructions see
the [User Guide](user-guide.md); for beat-tracking research and limitations see
[Beat Tracking](beat-tracking.md). Experimental branches and unmerged pull
requests are not part of this description.

## Architecture

The frontend is a React and TypeScript single-page application. The backend is
a FastAPI Python application. In development Vite serves the frontend and
proxies `/api` requests to the backend; a production frontend build can also
be served by the backend.

```text
Browser: React UI, video, Web Audio, guest localStorage
    | /api
    v
FastAPI routes -> application services -> SQLite + song files
                         |-> yt-dlp / ffmpeg
                         |-> Beat This! / Demucs / librosa
```

Entry points and important directories:

| Path                                            | Responsibility                                                     |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| `backend/src/music_trainer/app.py`              | Application factory, service construction, lifespan and routers    |
| `backend/src/music_trainer/api/`                | HTTP endpoints and dependency injection                            |
| `backend/src/music_trainer/services/`           | Downloads, analysis, playback assets, accounts and social features |
| `backend/src/music_trainer/models.py`           | Pydantic request, response and saved-data models                   |
| `backend/src/music_trainer/db.py`               | SQLAlchemy models, SQLite setup and schema updates                 |
| `backend/tests/`                                | pytest tests; `fakes.py` provides service substitutes              |
| `frontend/src/app/`                             | Routing and application shell                                      |
| `frontend/src/api/`                             | Typed API client and TypeScript models                             |
| `frontend/src/features/`                        | Feature UI, hooks and browser audio logic                          |
| `frontend/src/features/library/guestStorage.ts` | Guest library and settings in browser storage                      |
| `docs/` and `experiments/`                      | Documentation and separate feasibility experiments                 |

## Setup and running

### Prerequisites

- Python 3.11 or newer and Node.js 22 or newer.
- Python's standard-library `lzma` module, needed by the chord analysis
  dependencies. Check the interpreter with `python3 -c "import lzma"` (on
  Windows, `py -3.11 -c "import lzma"`). If this fails, use a Python build
  with LZMA support before creating the virtual environment.
- `ffmpeg` on `PATH`, or configured with `MUSIC_TRAINER_FFMPEG_PATH`.
- Deno is recommended for yt-dlp's YouTube JavaScript challenges; install it
  on `PATH` or set `MUSIC_TRAINER_DENO_PATH`.
- Internet access for YouTube and the initial model downloads, plus disk space
  for videos, model weights and stems.

The authoritative Python dependency declarations are in
`backend/pyproject.toml`; `backend/requirements.txt` installs that project with
development dependencies rather than maintaining a second list. The frontend
uses `frontend/package.json` and `package-lock.json`. On Linux, follow the
[README](../README.md#requirements) for CPU-only PyTorch installation if
needed.

### Install

From the repository root, Linux/macOS:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd ../frontend
npm ci
```

On Windows PowerShell, from the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
cd ..\frontend
npm ci
```

After dependency changes, repeat the relevant installation command in the
existing environment. `npm ci` uses the committed lockfile.

For a CPU-only PyTorch installation on Linux, first install compatible CPU
wheels into the virtual environment, then install the project:

```bash
# From backend/, with the virtual environment already created
.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e ".[dev]"
```

### Development servers

Before starting against existing data, read [Data and backups](#data-and-backups):
startup runs a cleanup that can delete unclaimed songs.

Use two terminals. On Linux/macOS, starting in the repository root:

```bash
# Terminal 1
cd backend
.venv/bin/uvicorn music_trainer.app:create_app --factory --reload
```

```bash
# Terminal 2
cd frontend
npm run dev
```

On Windows use `.venv\Scripts\uvicorn` in terminal 1. Visit
<http://localhost:5173>; the backend is at <http://127.0.0.1:8000>.
Stop each server with Ctrl+C. Vite proxies `/api` to the backend; set
`MUSIC_TRAINER_BACKEND_URL` for the Vite process if the backend uses another
address. The shell running `npm` must have Node.js on its `PATH`.

### Single server

Build the frontend with `npm run build` in `frontend/`, then run
`.venv/bin/music-trainer` in `backend/` (Windows:
`.venv\Scripts\music-trainer`). Open <http://127.0.0.1:8000>. The backend
serves `frontend/dist` when a build is present; rebuild after frontend changes.
Host and port settings apply to this entry point; pass explicit Uvicorn flags
when launching Uvicorn directly.

## Configuration

`Settings` in `backend/src/music_trainer/config.py` reads environment variables
prefixed `MUSIC_TRAINER_` and an optional `.env` in the server's working
directory. Important settings:

| Variable                                               | Default             | Purpose                                            |
| ------------------------------------------------------ | ------------------- | -------------------------------------------------- |
| `MUSIC_TRAINER_DATA_DIR`                               | repository `data/`  | Database, library and model weights                |
| `MUSIC_TRAINER_HOST`, `MUSIC_TRAINER_PORT`             | `127.0.0.1`, `8000` | Single-server bind address and port                |
| `MUSIC_TRAINER_FRONTEND_DIST_DIR`                      | `frontend/dist`     | Directory of the built frontend                    |
| `MUSIC_TRAINER_DENO_PATH`, `MUSIC_TRAINER_FFMPEG_PATH` | lookup on `PATH`    | External executables                               |
| `MUSIC_TRAINER_MAX_VIDEO_HEIGHT`                       | `720`               | Maximum download height                            |
| `MUSIC_TRAINER_MAX_PARALLEL_DOWNLOADS`                 | `2`                 | Concurrent downloads                               |
| `MUSIC_TRAINER_BEAT_MODEL`                             | `final0`            | Beat This! checkpoint, or comma-separated ensemble |
| `MUSIC_TRAINER_ANALYSIS_DEVICE`                        | `cpu`               | Beat model device, e.g. `cuda`                     |
| `MUSIC_TRAINER_ANALYZE_BEATS_AFTER_DOWNLOAD`           | `true`              | Start beat analysis after download                 |
| `MUSIC_TRAINER_STEM_MODEL`                             | `htdemucs_6s`       | Demucs model                                       |
| `MUSIC_TRAINER_SEPARATION_DEVICE`                      | `cpu`               | Stem model device, e.g. `cuda`                     |
| `MUSIC_TRAINER_SEPARATE_STEMS_AFTER_DOWNLOAD`          | `true`              | Start separation after download                    |
| `MUSIC_TRAINER_SESSION_DAYS`                           | `30`                | Session lifetime                                   |
| `MUSIC_TRAINER_SESSION_COOKIE_SECURE`                  | `false`             | Restrict the session cookie to HTTPS               |
| `MUSIC_TRAINER_GUEST_SONG_DAYS`                        | `7`                 | Guest retention for songs with no account owner    |

Disabling analysis or separation after download defers it until the song is
opened. `MUSIC_TRAINER_BACKEND_URL` is a Vite setting, not a backend setting.
See the [README configuration table](../README.md#configuration) and the
settings class for details and validation.

## Main data flow

1. Search uses yt-dlp; the client starts downloads through `/api/downloads`
   and polls their progress. Files are staged before entering the library.
2. After a successful download, configured background jobs analyze beats and
   separate stems. Beat This! produces activations, saved as
   `beat_activations.npz`; the decoder produces the shared `analysis.json`.
   User beat-grid hints can re-decode the stored activations.
3. A queue runs Demucs separation in a worker process. Completed FLAC tracks
   and metadata are saved under `stems/`. Chord analysis uses librosa chroma,
   aligns results to the beat grid, and caches them by grid.
4. The player normally uses a video element. For gapless loops a Signalsmith
   Stretch AudioWorklet plays a fetched audio buffer, while the video follows.
   Stems use separate buffer voices and gains with their own stretcher.
   `elementAudio.ts` shares an audio context for the video element.
5. The metronome schedules synthesized clicks ahead on the Web Audio clock,
   based on the beat grid and playback position. It follows the active loop or
   stem clock where applicable.
6. Account presets and player settings are saved through the personal-library
   API. Guest equivalents use browser localStorage. The frontend debounces
   saves and attempts to flush pending changes when leaving the page.

Detection and separation are estimates and may fail, take time or consume
substantial CPU and memory. See [Beat Tracking](beat-tracking.md) for the
decoder and its limitations.

## API

With the backend running, use <http://127.0.0.1:8000/docs> for interactive
OpenAPI documentation and `/openapi.json` for the schema. Examples:

```bash
curl http://127.0.0.1:8000/api/health
curl 'http://127.0.0.1:8000/api/search?q=guitar'
```

The search example needs internet and can fail if YouTube is unavailable.
Endpoint groups include:

| Prefix                          | Purpose                                                    |
| ------------------------------- | ---------------------------------------------------------- |
| `/api/auth`                     | Register, login, session, password and account deletion    |
| `/api/me/library`               | Account library, presets, settings, stars and guest import |
| `/api/me`                       | Profile settings, notifications and practice               |
| `/api/users`, `/api/feed`       | Profiles, follows and activity                             |
| `/api/search`, `/api/downloads` | Search and download jobs                                   |
| `/api/library/{video_id}`       | Media, audio windows, beats, stems, chords and comments    |

Register/login returns an HTTP-only `SameSite=Lax` session cookie. Passwords
are hashed with Argon2; only a hash of the session token is stored in SQLite.
Endpoints that require an account return 401 for a guest. Requests and
responses use the Pydantic models in `models.py`; the frontend client in
`frontend/src/api/client.ts` is the main consumer. Consult OpenAPI for exact
methods, payloads, query parameters and status codes.

## Data and backups

By default, data is outside Git in the repository's `data/` directory:

```text
data/
  music_trainer.db             accounts, sessions, libraries and social data
  library/<video-id>/          video, metadata, analysis and stems
  library/.staging/            downloads in progress
  models/                      downloaded model weights
```

Account-specific presets and settings live in SQLite, not in the shared song
folder. Guest library entries, presets and settings live in browser
localStorage and are not included in a server-side backup.

**Back up before upgrading or testing with existing data.** The server checks
song ownership on startup and hourly. A song without an account owner or a
recent guest-use record is eligible for deletion, including songs from older
versions that have no record in the new database. Account removal or deleting
the last account can also trigger deletion. Stopping the server and copying
the entire configured data directory gives a consistent offline backup;
protect it because the database contains user data. Restore it only with the
server stopped. For tests or experiments, set `MUSIC_TRAINER_DATA_DIR` to a
separate directory rather than the real library.

Schema initialization and incremental updates are implemented in `db.py`.
Review compatibility and back up data before changing or upgrading the schema;
do not assume that old on-disk player settings migrate automatically.

## Tests and checks

From `backend/`:

```bash
.venv/bin/pytest
.venv/bin/ruff check
```

On Windows, use `.venv\Scripts\pytest` and `.venv\Scripts\ruff`. Default pytest
excludes tests marked `network`. To opt in to tests that access real YouTube
or download the beat model, run `.venv/bin/pytest -m network` (use the Windows
path on Windows). Tests use temporary data and injected fake YouTube, beat,
stem and chord services; do not point manual tests at a user's data directory.

From `frontend/`:

```bash
npm test
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Use `npm run format` or the backend's `ruff format` when formatting is
intended; these commands modify files. The frontend test runner includes
`src/**/*.test.ts`. For focused tests, pass the desired test path after
`npm test --` or to pytest.

## Changing the application

- For backend behavior, update the relevant service and API route; extend
  Pydantic models and tests when the contract changes.
- Keep `frontend/src/api/types.ts` and `client.ts` consistent with backend
  request and response models, then update the relevant feature UI and tests.
- Preserve the shared video audio context when changing player routing. Test
  normal playback, loop takeover, seeks, speed changes, stems and metronome
  together when touching audio timing.
- For persistence changes, consider both guest localStorage and account
  storage, upgrades from existing data, cleanup behavior and failed saves.
- Update this guide and the [User Guide](user-guide.md) when behavior or setup
  changes.

## Deployment and troubleshooting

The development server binds to localhost by default. A built frontend can be
served by the backend, but public deployment needs additional security and
operational review; do not assume the development setup is production-ready.
When using HTTPS, enable the secure session cookie. Protect access to the data
directory and avoid exposing logs or credentials.

- If `/api/health` fails, check backend startup logs, the port and Python
  environment. If the UI cannot reach it, check Vite's proxy target.
- For download or analysis failures, check backend logs, internet, `ffmpeg`,
  Deno, model downloads, disk space and the configured device.
- If chord analysis fails with `No module named '_lzma'`, the Python
  interpreter itself lacks LZMA support; reinstall or use a complete Python
  3.11+ build and create a new virtual environment with it, then reinstall
  the backend dependencies. Installing `librosa` alone will not fix this.
- Browser autoplay policy, mute/output settings, Web Audio/AudioWorklet support
  and tab scheduling can affect playback and metronome timing.
- Stems are resource-intensive; check queue status and memory if loading or
  separation fails. Analysis quality and chord names are not guaranteed.
