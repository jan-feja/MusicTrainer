"""Downloaded videos on disk, one folder per video.

    <library>/<video_id>/meta.json       VideoMetadata
    <library>/<video_id>/video.mp4       media file (its name is stored in meta.json)
    <library>/<video_id>/thumbnail.jpg   optional
    <library>/<video_id>/analysis.json   BeatAnalysis (beats and bar starts), once detected
    <library>/<video_id>/beat_activations.npz  beat network output, to decode again with new hints
    <library>/<video_id>/loops.json      the user's saved loops (list of SavedLoop)
    <library>/<video_id>/player.json     how the player was left (PlayerSettings, with the mixer)
    <library>/<video_id>/stems/          separated instruments: stems.json (StemSet), one FLAC each
    <library>/<video_id>/chords.json     ChordAnalysis (chords on the beat grid), once detected
    <library>/.staging/<video_id>/       downloads in progress, moved into place when done

Stems are FLAC, lossless: AAC or Opus would shift them in time against each
other. They are written to stems.partial/ and renamed to stems/ when complete.
"""

import logging
import shutil
import threading
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import numpy as np
from pydantic import BaseModel, TypeAdapter, ValidationError

from music_trainer.models import (
    BeatAnalysis,
    ChordAnalysis,
    PlayerSettings,
    SavedLoop,
    StemSet,
    VideoMetadata,
)
from music_trainer.services.beat_decoding import BeatActivations
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
    LOOPS_FILE = "loops.json"
    SETTINGS_FILE = "player.json"
    STEMS_DIR = "stems"
    STEMS_STAGING_DIR = "stems.partial"
    STEMS_FILE = "stems.json"
    CHORDS_FILE = "chords.json"
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

    def read_chords(self, video_id: str) -> ChordAnalysis | None:
        return self._read_json(self._video_dir(video_id) / self.CHORDS_FILE, ChordAnalysis)

    def write_chords(self, video_id: str, chords: ChordAnalysis) -> None:
        self._write_text(video_id, self.CHORDS_FILE, chords.model_dump_json())

    def stem_paths(self, video_id: str, names: Sequence[str]) -> list[Path]:
        """The audio files of those of the named stems that were separated."""
        paths = (self.stem_path(video_id, name) for name in names)
        return [path for path in paths if path is not None]

    def read_stems(self, video_id: str) -> StemSet | None:
        """The separated stems, or None if there are none (or a file is missing)."""
        folder = self._video_dir(video_id) / self.STEMS_DIR
        stems = self._read_json(folder / self.STEMS_FILE, StemSet)
        if stems is None:
            return None
        if not all(self._file_in(folder, stem.file) for stem in stems.stems):
            logger.warning("Ignoring stems of %s: a file is missing", video_id)
            return None
        return stems

    def stem_path(self, video_id: str, name: str) -> Path | None:
        """The audio file of one stem, or None if there is no such stem."""
        stems = self.read_stems(video_id)
        stem = next((s for s in stems.stems if s.name == name), None) if stems else None
        if stem is None:
            return None
        return self._file_in(self._video_dir(video_id) / self.STEMS_DIR, stem.file)

    def create_stems_staging_dir(self, video_id: str) -> Path:
        """An empty folder in the video's folder to separate the stems into."""
        if not self.contains(video_id):
            raise VideoNotInLibraryError(video_id)
        folder = self._video_dir(video_id) / self.STEMS_STAGING_DIR
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir()
        return folder

    def commit_stems(self, video_id: str, stems: StemSet) -> None:
        """Replace the video's stems with the ones in its staging folder."""
        if not self.contains(video_id):
            raise VideoNotInLibraryError(video_id)
        folder = self._video_dir(video_id)
        staging = folder / self.STEMS_STAGING_DIR
        (staging / self.STEMS_FILE).write_text(stems.model_dump_json(indent=2), encoding="utf-8")
        with self._lock:
            target = folder / self.STEMS_DIR
            if target.exists():
                shutil.rmtree(target)
            staging.rename(target)

    def discard_stems_staging(self, video_id: str) -> None:
        shutil.rmtree(self._video_dir(video_id) / self.STEMS_STAGING_DIR, ignore_errors=True)

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
        return self._file_in(self._video_dir(video_id), file_name)

    @staticmethod
    def _file_in(folder: Path, file_name: str) -> Path | None:
        path = folder / file_name
        # file names come from JSON files; never let them point outside the folder
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
