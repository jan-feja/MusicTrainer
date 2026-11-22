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
from music_trainer.api import beats, downloads, library, search, stems
from music_trainer.api.dependencies import Services
from music_trainer.config import Settings
from music_trainer.services.audio import ffmpeg_executable
from music_trainer.services.beat_analysis import BeatAnalysisManager
from music_trainer.services.beats import BeatThisTracker, BeatTracker
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library
from music_trainer.services.stem_separation import StemSeparationManager
from music_trainer.services.stems import DemucsSeparator, StemSeparator
from music_trainer.services.youtube import YouTubeClient, YtDlpClient

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    youtube: YouTubeClient | None = None,
    beat_tracker: BeatTracker | None = None,
    stem_separator: StemSeparator | None = None,
) -> FastAPI:
    """Create the app. Tests pass their own settings and fakes for YouTube and the models."""
    settings = settings or Settings()
    video_library = Library(settings.library_dir)
    video_library.clear_staging()
    if youtube is None:
        _warn_about_missing_tools(settings)
        youtube = YtDlpClient(settings.max_video_height, settings.deno_path, settings.ffmpeg_path)
    if beat_tracker is None:
        beat_tracker = BeatThisTracker(
            settings.beat_model,
            settings.models_dir,
            settings.analysis_device,
            ffmpeg_executable(settings.ffmpeg_path),
        )
    beat_analysis = BeatAnalysisManager(beat_tracker, video_library)
    if stem_separator is None:
        stem_separator = DemucsSeparator(
            settings.stem_model,
            settings.models_dir,
            settings.separation_device,
            ffmpeg_executable(settings.ffmpeg_path),
        )
    stem_separation = StemSeparationManager(stem_separator, video_library)

    def after_download(video_id: str) -> None:
        if settings.analyze_beats_after_download:
            beat_analysis.start(video_id)
        if settings.separate_stems_after_download:
            stem_separation.start(video_id)

    download_manager = DownloadManager(
        youtube, video_library, settings.max_parallel_downloads, on_completed=after_download
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        download_manager.shutdown()
        beat_analysis.shutdown()
        stem_separation.shutdown()

    app = FastAPI(title="Music Trainer", version=__version__, lifespan=lifespan)
    app.state.services = Services(
        settings, video_library, youtube, download_manager, beat_analysis, stem_separation
    )

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(search.router)
    app.include_router(library.router)
    app.include_router(downloads.router)
    app.include_router(beats.router)
    app.include_router(stems.router)
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
