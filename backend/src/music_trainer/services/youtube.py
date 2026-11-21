"""YouTube access through yt-dlp: search and download."""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import yt_dlp
from yt_dlp.utils import DownloadError

from music_trainer.models import SearchResult, VideoMetadata
from music_trainer.video_ids import (
    default_thumbnail_url,
    is_valid_video_id,
    video_id_from_url,
    watch_url,
)

logger = logging.getLogger(__name__)

MEDIA_BASENAME = "video"
THUMBNAIL_BASENAME = "thumbnail"
_PREFERRED_THUMBNAIL_WIDTH = 480
_ERROR_PREFIX_RE = re.compile(r"^(?:ERROR:\s*)?(?:\[[^\]]+\]\s*(?:[\w-]+:\s*)?)?")


class YouTubeError(Exception):
    """YouTube refused or failed the request (video unavailable, network error, ...)."""


@dataclass(frozen=True)
class DownloadProgress:
    phase: Literal["downloading", "processing"]
    fraction: float
    """Share of the whole download that is done, 0..1."""


ProgressCallback = Callable[[DownloadProgress], None]


class YouTubeClient(Protocol):
    """What the app needs from YouTube. Tests replace it with a fake."""

    def search(self, query: str, limit: int) -> list[SearchResult]: ...

    def download(
        self, video_id: str, target_dir: Path, on_progress: ProgressCallback
    ) -> VideoMetadata: ...


class YtDlpClient:
    """YouTubeClient backed by yt-dlp."""

    def __init__(
        self,
        max_video_height: int = 720,
        deno_path: Path | None = None,
        ffmpeg_path: Path | None = None,
    ) -> None:
        self._max_video_height = max_video_height
        self._deno_path = deno_path
        self._ffmpeg_path = ffmpeg_path

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Search YouTube. A pasted video link returns that single video."""
        video_id = video_id_from_url(query)
        try:
            if video_id:
                with yt_dlp.YoutubeDL(self._options()) as ydl:
                    entries = [ydl.extract_info(watch_url(video_id), download=False, process=False)]
            else:
                # extract_flat: read the result list only, without opening every video
                with yt_dlp.YoutubeDL(self._options(extract_flat="in_playlist")) as ydl:
                    info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                entries = info.get("entries") or []
        except DownloadError as error:
            raise YouTubeError(clean_error_message(error)) from error
        return [result for entry in entries if (result := search_result_from_entry(entry))]

    def download(
        self, video_id: str, target_dir: Path, on_progress: ProgressCallback
    ) -> VideoMetadata:
        """Download the video (with audio) and its thumbnail into `target_dir`."""
        tracker = _ProgressTracker(on_progress)
        options = self._options(
            format=self._format_selector(),
            merge_output_format="mp4",
            outtmpl={
                "default": str(target_dir / f"{MEDIA_BASENAME}.%(ext)s"),
                "thumbnail": str(target_dir / f"{THUMBNAIL_BASENAME}.%(ext)s"),
            },
            writethumbnail=True,
            postprocessors=[{"key": "FFmpegThumbnailsConvertor", "format": "jpg"}],
            progress_hooks=[tracker.on_download_progress],
            postprocessor_hooks=[tracker.on_postprocessor_progress],
        )
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                # Pick the streams first, so progress can be weighted by their sizes.
                info = ydl.extract_info(watch_url(video_id), download=False)
                tracker.set_streams(info.get("requested_formats") or [info])
                info = ydl.process_ie_result(info, download=True)
        except DownloadError as error:
            raise YouTubeError(clean_error_message(error)) from error

        media_path = Path(info["requested_downloads"][0]["filepath"])
        thumbnail_path = target_dir / f"{THUMBNAIL_BASENAME}.jpg"
        return metadata_from_info(
            info,
            media_file=media_path.name,
            thumbnail_file=thumbnail_path.name if thumbnail_path.is_file() else None,
        )

    def _format_selector(self) -> str:
        height = self._max_video_height
        # H.264 video + AAC audio in MP4 plays in every browser; fall back to anything.
        return (
            f"bv*[vcodec^=avc1][height<={height}]+ba[ext=m4a]"
            f"/b[ext=mp4][height<={height}]"
            f"/bv*[height<={height}]+ba"
            "/b"
        )

    def _options(self, **extra: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "logger": _YtDlpLogger(),
            "noprogress": True,
            "noplaylist": True,
        }
        if self._deno_path:
            options["js_runtimes"] = {"deno": {"path": str(self._deno_path)}}
        if self._ffmpeg_path:
            options["ffmpeg_location"] = str(self._ffmpeg_path)
        options.update(extra)
        return options


def search_result_from_entry(entry: Mapping[str, Any]) -> SearchResult | None:
    """Convert one yt-dlp search entry; None for anything that is not a video."""
    video_id = entry.get("id")
    if not isinstance(video_id, str) or not is_valid_video_id(video_id):
        return None
    return SearchResult(
        video_id=video_id,
        title=entry.get("title") or video_id,
        channel=entry.get("channel") or entry.get("uploader"),
        duration_seconds=entry.get("duration"),
        view_count=entry.get("view_count"),
        thumbnail_url=pick_thumbnail_url(entry.get("thumbnails") or [])
        or default_thumbnail_url(video_id),
    )


def metadata_from_info(
    info: Mapping[str, Any], media_file: str, thumbnail_file: str | None
) -> VideoMetadata:
    video_id = info["id"]
    return VideoMetadata(
        video_id=video_id,
        title=info.get("title") or video_id,
        channel=info.get("channel") or info.get("uploader"),
        duration_seconds=info.get("duration"),
        upload_date=parse_upload_date(info.get("upload_date")),
        view_count=info.get("view_count"),
        description=info.get("description"),
        source_url=info.get("webpage_url") or watch_url(video_id),
        media_file=media_file,
        thumbnail_file=thumbnail_file,
    )


def pick_thumbnail_url(thumbnails: Sequence[Mapping[str, Any]]) -> str | None:
    """The thumbnail closest to card size; thumbnails without a width count as small."""
    candidates = [t for t in thumbnails if t.get("url")]
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda t: abs((t.get("width") or 0) - _PREFERRED_THUMBNAIL_WIDTH),
    )
    return best["url"]


def parse_upload_date(value: str | None) -> date | None:
    """yt-dlp dates look like '20240131'."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def clean_error_message(error: Exception) -> str:
    """'ERROR: [youtube] abc: Video unavailable' -> 'Video unavailable'."""
    return _ERROR_PREFIX_RE.sub("", str(error)).strip() or "YouTube request failed"


class _ProgressTracker:
    """Combines yt-dlp's per-stream progress into one 0..1 value.

    YouTube serves video and audio as separate streams that are downloaded one
    after the other and merged. Each stream counts by its file size (equally
    when sizes are unknown).
    """

    def __init__(self, callback: ProgressCallback) -> None:
        self._callback = callback
        self._weights: dict[str, float] = {}
        self._finished: set[str] = set()

    def set_streams(self, formats: Sequence[Mapping[str, Any]]) -> None:
        sizes = [f.get("filesize") or f.get("filesize_approx") or 0 for f in formats]
        total = sum(sizes)
        for stream, size in zip(formats, sizes, strict=True):
            share = size / total if total and all(sizes) else 1 / len(formats)
            self._weights[str(stream.get("format_id"))] = share

    def on_download_progress(self, status: Mapping[str, Any]) -> None:
        format_id = str(status.get("info_dict", {}).get("format_id"))
        if status.get("status") == "finished":
            self._finished.add(format_id)
            current = 0.0
        elif status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            current = min(status.get("downloaded_bytes", 0) / total, 1.0) if total else 0.0
        else:
            return

        if not self._weights:  # streams unknown: report the current stream alone
            fraction = 1.0 if format_id in self._finished else current
        else:
            done = sum(w for fid, w in self._weights.items() if fid in self._finished)
            running = 0.0 if format_id in self._finished else self._weights.get(format_id, 0.0)
            fraction = done + running * current
        self._callback(DownloadProgress("downloading", min(fraction, 1.0)))

    def on_postprocessor_progress(self, status: Mapping[str, Any]) -> None:
        if status.get("status") == "started" and status.get("postprocessor") == "Merger":
            self._callback(DownloadProgress("processing", 1.0))


class _YtDlpLogger:
    """Routes yt-dlp's console output to Python logging."""

    def debug(self, message: str) -> None:
        logger.debug(message)

    def info(self, message: str) -> None:
        logger.debug(message)

    def warning(self, message: str) -> None:
        logger.warning(message)

    def error(self, message: str) -> None:
        logger.error(message)
