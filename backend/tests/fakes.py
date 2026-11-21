"""Test doubles and helpers shared by the tests."""

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from music_trainer.models import BeatAnalysis, SearchResult, VideoMetadata
from music_trainer.services.beats import BeatTrackingError, beat_analysis_from_times
from music_trainer.services.youtube import DownloadProgress, ProgressCallback, YouTubeError
from music_trainer.video_ids import watch_url

VIDEO_ID = "jNQXAC9IVRw"
OTHER_VIDEO_ID = "dQw4w9WgXcQ"
FAKE_MEDIA = bytes(range(256)) * 40  # 10 240 bytes
# 120 BPM, 4/4: 16 beats, bars starting every 2 s
FAKE_BEATS = beat_analysis_from_times(
    [0.5 + 0.5 * i for i in range(16)], [0.5 + 2.0 * i for i in range(4)], analyzer="fake"
)


class FakeYouTubeClient:
    """Stands in for YtDlpClient: no network, instant downloads."""

    def __init__(self) -> None:
        self.search_results = [
            SearchResult(
                video_id=VIDEO_ID, title="Me at the zoo", channel="jawed", duration_seconds=19
            ),
            SearchResult(video_id=OTHER_VIDEO_ID, title="Another video", duration_seconds=213),
        ]
        self.queries: list[str] = []
        self.error: str | None = None
        """When set, search and download raise YouTubeError with this message."""
        self.release_download = threading.Event()
        """Downloads wait for this event; set by default so they finish at once."""
        self.release_download.set()

    def search(self, query: str, limit: int) -> list[SearchResult]:
        self.queries.append(query)
        if self.error:
            raise YouTubeError(self.error)
        return self.search_results[:limit]

    def download(
        self, video_id: str, target_dir: Path, on_progress: ProgressCallback
    ) -> VideoMetadata:
        on_progress(DownloadProgress("downloading", 0.5))
        self.release_download.wait(timeout=10)
        if self.error:
            raise YouTubeError(self.error)
        (target_dir / "video.mp4").write_bytes(FAKE_MEDIA)
        (target_dir / "thumbnail.jpg").write_bytes(b"jpeg")
        on_progress(DownloadProgress("processing", 1.0))
        return VideoMetadata(
            video_id=video_id,
            title=f"Video {video_id}",
            duration_seconds=19,
            source_url=watch_url(video_id),
            media_file="video.mp4",
            thumbnail_file="thumbnail.jpg",
        )


class FakeBeatTracker:
    """Stands in for BeatThisTracker: no model, instant result."""

    def __init__(self) -> None:
        self.analyzed: list[Path] = []
        self.error: str | None = None
        """When set, analyze() raises BeatTrackingError with this message."""
        self.release = threading.Event()
        """analyze() waits for this event; set by default so it finishes at once."""
        self.release.set()

    def analyze(self, media_path: Path) -> BeatAnalysis:
        self.analyzed.append(media_path)
        self.release.wait(timeout=10)
        if self.error:
            raise BeatTrackingError(self.error)
        return FAKE_BEATS


def wait_for_download(client: TestClient, video_id: str, timeout: float = 5.0) -> dict:
    """Poll the download until it is no longer active; return the final job."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/downloads/{video_id}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"download of {video_id} did not finish within {timeout} s")


def wait_for_beats(client: TestClient, video_id: str, timeout: float = 5.0) -> dict:
    """Poll beat detection until it is no longer queued or running; return the final state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/api/library/{video_id}/beats").json()
        if state["status"] not in ("queued", "analyzing"):
            return state
        time.sleep(0.02)
    raise AssertionError(f"beat detection of {video_id} did not finish within {timeout} s")
