"""Downloaded videos on disk, one folder per video.

    <library>/<video_id>/meta.json       VideoMetadata
    <library>/<video_id>/video.mp4       media file (its name is stored in meta.json)
    <library>/<video_id>/thumbnail.jpg   optional
    <library>/.staging/<video_id>/       downloads in progress, moved into place when done

Later features (stems, analysis.json, loops.json) belong in the same folder.
"""

import logging
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from music_trainer.models import VideoMetadata
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)


class LibraryError(Exception):
    """A library operation failed, e.g. a file is still in use."""


class Library:
    METADATA_FILE = "meta.json"
    STAGING_DIR = ".staging"

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = threading.Lock()
        root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def list_videos(self) -> list[VideoMetadata]:
        """All videos, most recently downloaded first."""
        videos = [
            metadata
            for folder in self._root.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
            if (metadata := self._read_metadata(folder)) is not None
        ]
        videos.sort(key=lambda v: v.downloaded_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return videos

    def get_video(self, video_id: str) -> VideoMetadata | None:
        return self._read_metadata(self._video_dir(video_id))

    def contains(self, video_id: str) -> bool:
        return (self._video_dir(video_id) / self.METADATA_FILE).is_file()

    def media_path(self, video_id: str) -> Path | None:
        metadata = self.get_video(video_id)
        return self._file_in_video_dir(video_id, metadata.media_file) if metadata else None

    def thumbnail_path(self, video_id: str) -> Path | None:
        metadata = self.get_video(video_id)
        if metadata is None or metadata.thumbnail_file is None:
            return None
        return self._file_in_video_dir(video_id, metadata.thumbnail_file)

    def delete_video(self, video_id: str) -> bool:
        """Delete the video's folder. Returns False if there was nothing to delete."""
        folder = self._video_dir(video_id)
        if not folder.exists():
            return False
        try:
            shutil.rmtree(folder)
        except OSError as error:  # on Windows: file still open, e.g. being played
            raise LibraryError(f"Could not delete {video_id}: {error.strerror}") from error
        return True

    def create_staging_dir(self, video_id: str) -> Path:
        """An empty folder to download into."""
        folder = self._staging_dir(video_id)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        return folder

    def commit(self, video_id: str, metadata: VideoMetadata) -> VideoMetadata:
        """Move a finished download from staging into the library."""
        staging = self._staging_dir(video_id)
        metadata = metadata.model_copy(update={"downloaded_at": datetime.now(UTC)})
        (staging / self.METADATA_FILE).write_text(
            metadata.model_dump_json(indent=2), encoding="utf-8"
        )
        with self._lock:
            target = self._video_dir(video_id)
            if target.exists():
                shutil.rmtree(target)
            staging.rename(target)
        return metadata

    def discard_staging(self, video_id: str) -> None:
        shutil.rmtree(self._staging_dir(video_id), ignore_errors=True)

    def clear_staging(self) -> None:
        """Remove downloads left over from a previous run."""
        shutil.rmtree(self._root / self.STAGING_DIR, ignore_errors=True)

    def _video_dir(self, video_id: str) -> Path:
        return self._root / require_valid_video_id(video_id)

    def _staging_dir(self, video_id: str) -> Path:
        return self._root / self.STAGING_DIR / require_valid_video_id(video_id)

    def _file_in_video_dir(self, video_id: str, file_name: str) -> Path | None:
        folder = self._video_dir(video_id)
        path = folder / file_name
        # file names come from meta.json; never let them point outside the folder
        if path.parent != folder or not path.is_file():
            return None
        return path

    def _read_metadata(self, folder: Path) -> VideoMetadata | None:
        path = folder / self.METADATA_FILE
        if not path.is_file():
            return None
        try:
            return VideoMetadata.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            logger.warning("Skipping unreadable %s: %s", path, error)
            return None
