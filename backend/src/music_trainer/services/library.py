"""Downloaded videos on disk, one folder per video.

    <library>/<video_id>/meta.json       VideoMetadata
    <library>/<video_id>/video.mp4       media file (its name is stored in meta.json)
    <library>/<video_id>/thumbnail.jpg   optional
    <library>/<video_id>/analysis.json   BeatAnalysis (beats and bar starts), once detected
    <library>/<video_id>/beat_activations.npz  beat network output, to decode again with new hints
    <library>/<video_id>/loops.json      the user's saved loops (list of SavedLoop)
    <library>/<video_id>/player.json     how the player was left (PlayerSettings)
    <library>/.staging/<video_id>/       downloads in progress, moved into place when done

Later features (stems, ...) belong in the same folder.
"""

import logging
import shutil
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import numpy as np
from pydantic import BaseModel, TypeAdapter, ValidationError

from music_trainer.models import BeatAnalysis, PlayerSettings, SavedLoop, VideoMetadata
from music_trainer.services.beat_decoding import BeatActivations
from music_trainer.services.visual import VERSION as PICTURE_VERSION
from music_trainer.services.visual import MusicPicture
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)
DELETE_ATTEMPTS = 5
DELETE_RETRY_SECONDS = 0.1
_LOOP_LIST = TypeAdapter(list[SavedLoop])


class LibraryError(Exception):
    """A library operation failed, e.g. a file is still in use."""


class VideoNotInLibraryError(LibraryError, LookupError):
    def __init__(self, video_id: str) -> None:
        super().__init__(f"Video {video_id} is not in the library")


class Library:
    METADATA_FILE = "meta.json"
    ANALYSIS_FILE = "analysis.json"
    ACTIVATIONS_FILE = "beat_activations.npz"
    PICTURE_FILE = "visual.npz"
    LOOPS_FILE = "loops.json"
    SETTINGS_FILE = "player.json"
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

    def read_beat_analysis(self, video_id: str) -> BeatAnalysis | None:
        return self._read_json(self._video_dir(video_id) / self.ANALYSIS_FILE, BeatAnalysis)

    def write_beat_analysis(self, video_id: str, analysis: BeatAnalysis) -> None:
        self._write_text(video_id, self.ANALYSIS_FILE, analysis.model_dump_json())

    def read_loops(self, video_id: str) -> list[SavedLoop]:
        """The saved loops; empty if there are none (or the file is unreadable)."""
        path = self._video_dir(video_id) / self.LOOPS_FILE
        if not path.is_file():
            return []
        try:
            return _LOOP_LIST.validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            logger.warning("Ignoring unreadable %s: %s", path, error)
            return []

    def write_loops(self, video_id: str, loops: list[SavedLoop]) -> None:
        self._write_text(video_id, self.LOOPS_FILE, _LOOP_LIST.dump_json(loops, indent=2).decode())

    def read_player_settings(self, video_id: str) -> PlayerSettings | None:
        return self._read_json(self._video_dir(video_id) / self.SETTINGS_FILE, PlayerSettings)

    def write_player_settings(self, video_id: str, settings: PlayerSettings) -> None:
        self._write_text(video_id, self.SETTINGS_FILE, settings.model_dump_json(indent=2))

    def read_beat_activations(self, video_id: str) -> BeatActivations | None:
        """The stored beat network output, or None if missing or unreadable."""
        path = self._video_dir(video_id) / self.ACTIVATIONS_FILE
        try:
            with np.load(path) as data:
                return BeatActivations(
                    beat=data["beat"].astype(np.float32),
                    downbeat=data["downbeat"].astype(np.float32),
                    fps=float(data["fps"]),
                    model=str(data["model"]),
                )
        except FileNotFoundError:
            return None
        except (OSError, KeyError, ValueError) as error:
            logger.warning("Ignoring unreadable %s: %s", path, error)
            return None

    def write_beat_activations(self, video_id: str, activations: BeatActivations) -> None:
        if not self.contains(video_id):
            raise VideoNotInLibraryError(video_id)
        target = self._video_dir(video_id) / self.ACTIVATIONS_FILE
        partial = target.with_name(target.name + ".part")
        with partial.open("wb") as file:  # a file object keeps numpy from adding ".npz"
            np.savez_compressed(
                file,
                beat=activations.beat.astype(np.float16),  # logits; 3 significant digits are plenty
                downbeat=activations.downbeat.astype(np.float16),
                fps=np.float64(activations.fps),
                model=np.str_(activations.model),
            )
        partial.replace(target)

    def read_picture(self, video_id: str) -> MusicPicture | None:
        """The stored picture of the music, or None if missing, unreadable or outdated."""
        path = self._video_dir(video_id) / self.PICTURE_FILE
        try:
            with np.load(path) as data:
                if int(data["version"]) != PICTURE_VERSION:
                    return None
                return MusicPicture(
                    spectrogram=data["spectrogram"],
                    colors=data["colors"],
                    fps=float(data["fps"]),
                    color_step=float(data["color_step"]),
                )
        except FileNotFoundError:
            return None
        except (OSError, KeyError, ValueError) as error:
            logger.warning("Ignoring unreadable %s: %s", path, error)
            return None

    def write_picture(self, video_id: str, picture: MusicPicture) -> None:
        if not self.contains(video_id):
            raise VideoNotInLibraryError(video_id)
        target = self._video_dir(video_id) / self.PICTURE_FILE
        partial = target.with_name(target.name + ".part")
        with partial.open("wb") as file:
            np.savez_compressed(
                file,
                spectrogram=picture.spectrogram,
                colors=picture.colors,
                fps=np.float64(picture.fps),
                color_step=np.float64(picture.color_step),
                version=np.int64(PICTURE_VERSION),
            )
        partial.replace(target)

    def delete_video(self, video_id: str) -> bool:
        """Delete the video's folder. Returns False if there was nothing to delete."""
        folder = self._video_dir(video_id)
        if not folder.exists():
            return False
        for attempt in range(DELETE_ATTEMPTS):
            try:
                shutil.rmtree(folder)
                return True
            except OSError as error:
                # on Windows, files open elsewhere cannot be deleted: a background job writing
                # into the folder is done in a moment, a video being played stays open
                if attempt == DELETE_ATTEMPTS - 1:
                    message = f"Could not delete {video_id}: {error.strerror}"
                    raise LibraryError(message) from error
                time.sleep(DELETE_RETRY_SECONDS)
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

    def _write_text(self, video_id: str, file_name: str, text: str) -> None:
        if not self.contains(video_id):
            raise VideoNotInLibraryError(video_id)
        target = self._video_dir(video_id) / file_name
        partial = target.with_name(target.name + ".part")
        partial.write_text(text, encoding="utf-8")
        partial.replace(target)  # readers never see a half-written file

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
        return self._read_json(folder / self.METADATA_FILE, VideoMetadata)

    @staticmethod
    def _read_json(path: Path, model: type[ModelT]) -> ModelT | None:
        if not path.is_file():
            return None
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            logger.warning("Skipping unreadable %s: %s", path, error)
            return None
