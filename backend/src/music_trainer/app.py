"""Builds the FastAPI application."""

import logging
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from music_trainer import __version__
from music_trainer.api import downloads, library, search
from music_trainer.api.dependencies import Services
from music_trainer.config import Settings
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library
from music_trainer.services.youtube import YouTubeClient, YtDlpClient

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, youtube: YouTubeClient | None = None) -> FastAPI:
    """Create the app. Tests pass their own settings and a fake YouTube client."""
    settings = settings or Settings()
    video_library = Library(settings.library_dir)
    video_library.clear_staging()
    if youtube is None:
        _warn_about_missing_tools(settings)
        youtube = YtDlpClient(settings.max_video_height, settings.deno_path, settings.ffmpeg_path)
    download_manager = DownloadManager(youtube, video_library, settings.max_parallel_downloads)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        download_manager.shutdown()

    app = FastAPI(title="Music Trainer", version=__version__, lifespan=lifespan)
    app.state.services = Services(settings, video_library, youtube, download_manager)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(search.router)
    app.include_router(library.router)
    app.include_router(downloads.router)
    _serve_frontend(app, settings.frontend_dist_dir)
    return app


def _serve_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Serve the built single-page app; any non-API path returns index.html."""
    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        logger.info("No frontend build in %s; serving the API only", dist_dir)
        return
    dist_dir = dist_dir.resolve()
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def single_page_app(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        file = (dist_dir / path).resolve()
        if path and file.is_file() and file.is_relative_to(dist_dir):
            return FileResponse(file)
        return FileResponse(index_file)


def _warn_about_missing_tools(settings: Settings) -> None:
    if settings.ffmpeg_path is None and shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found: downloads cannot merge video and audio")
    if settings.deno_path is None and shutil.which("deno") is None:
        logger.warning(
            "Deno not found: yt-dlp needs it for YouTube (some videos may fail). "
            "Install Deno or set MUSIC_TRAINER_DENO_PATH."
        )
