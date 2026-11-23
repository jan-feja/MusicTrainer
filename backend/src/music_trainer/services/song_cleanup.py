"""Deleting songs nobody has any more.

A song stays while some account has it in its library. Guests keep their
library in the browser, so for them the server only knows when a guest last
downloaded or opened a song: a song no account has is deleted once no guest
has used it for `guest_keep` (7 days by default).

`release` runs when an account lets go of a song; `sweep` checks every song, at
startup and then every hour.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from music_trainer.services.accounts import utc_now
from music_trainer.services.beat_analysis import BeatAnalysisManager
from music_trainer.services.chord_detection import ChordDetectionManager
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library, LibraryError
from music_trainer.services.stem_separation import StemSeparationManager
from music_trainer.services.user_library import UserLibrary

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 3600.0


class SongCleanup:
    def __init__(
        self,
        library: Library,
        user_library: UserLibrary,
        downloads: DownloadManager,
        beat_analysis: BeatAnalysisManager,
        stem_separation: StemSeparationManager,
        chord_detection: ChordDetectionManager,
        guest_keep: timedelta,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._library = library
        self._user_library = user_library
        self._downloads = downloads
        self._beat_analysis = beat_analysis
        self._stem_separation = stem_separation
        self._chord_detection = chord_detection
        self._guest_keep = guest_keep
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def release(self, video_id: str) -> bool:
        """Delete the song if nobody has it any more. Returns True if it was deleted."""
        with self._lock:
            if self._is_kept(video_id):
                return False
            try:
                return self._remove(video_id)
            except LibraryError as error:  # e.g. still open on Windows; the next sweep retries
                logger.warning("%s", error)
                return False

    def sweep(self) -> list[str]:
        """Delete every song nobody has; returns their IDs."""
        video_ids = [video.video_id for video in self._library.list_videos()]
        return [video_id for video_id in video_ids if self.release(video_id)]

    def start(self, interval_seconds: float = SWEEP_INTERVAL_SECONDS) -> None:
        """Sweep now, then every `interval_seconds` in a background thread."""
        self._run_sweep()

        def run() -> None:
            while not self._stop.wait(interval_seconds):
                self._run_sweep()

        self._thread = threading.Thread(target=run, name="song-cleanup", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()

    def _is_kept(self, video_id: str) -> bool:
        if self._user_library.has_owner(video_id):
            return True
        job = self._downloads.get(video_id)
        if job is not None and job.status.is_active:
            return True
        last_guest_use = self._user_library.last_guest_use(video_id)
        return last_guest_use is not None and self._clock() - last_guest_use < self._guest_keep

    def _remove(self, video_id: str) -> bool:
        self._stem_separation.forget(video_id)  # stops a separation writing into the folder
        deleted = self._library.delete_video(video_id)
        # so the video can be downloaded and analysed again
        self._downloads.forget(video_id)
        self._beat_analysis.forget(video_id)
        self._chord_detection.forget(video_id)
        self._user_library.forget_song(video_id)
        if deleted:
            logger.info("Deleted %s: nobody has it any more", video_id)
        return deleted

    def _run_sweep(self) -> None:
        try:
            self.sweep()
        except Exception:  # the next sweep tries again
            logger.exception("Cleaning up songs failed")
