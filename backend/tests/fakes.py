"""Test doubles and helpers shared by the tests."""

import itertools
import threading
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from music_trainer.models import Chord, SearchResult, StemInfo, StemSet, VideoMetadata
from music_trainer.services.beat_decoding import FRAMES_PER_SECOND, BeatActivations
from music_trainer.services.beats import BeatTrackingError, analyze_activations
from music_trainer.services.chords import ChordDetectionError
from music_trainer.services.stems import ProgressCallback as StemProgressCallback
from music_trainer.services.stems import StemSeparationError
from music_trainer.services.youtube import DownloadProgress, ProgressCallback, YouTubeError
from music_trainer.video_ids import watch_url

VIDEO_ID = "jNQXAC9IVRw"
OTHER_VIDEO_ID = "dQw4w9WgXcQ"
FAKE_MEDIA = bytes(range(256)) * 40  # 10 240 bytes


def network_output(
    beats: list[float],
    downbeats: list[float],
    seconds: float,
    beat_strength: float = 0.95,
    extra_downbeats: dict[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Logits like the beat network gives: a short bump at every beat, another at bar starts.

    `extra_downbeats` adds false bar starts {time: probability}.
    """
    t = np.arange(int(seconds * FRAMES_PER_SECOND)) / FRAMES_PER_SECOND
    beat = np.full_like(t, 0.002)  # what the network outputs between beats
    bar = np.full_like(t, 0.002)
    bump = lambda at, height: height * np.exp(-0.5 * ((t - at) * FRAMES_PER_SECOND / 0.8) ** 2)  # noqa: E731
    for b in beats:
        beat = np.maximum(beat, bump(b, beat_strength))
    for d in downbeats:
        bar = np.maximum(bar, bump(d, 0.9))
    for d, height in (extra_downbeats or {}).items():
        bar = np.maximum(bar, bump(d, height))
    logit = lambda p: np.log(p / (1 - p))  # noqa: E731
    return logit(np.clip(beat, 1e-6, 1 - 1e-6)), logit(np.clip(bar, 1e-6, 1 - 1e-6))


# 120 BPM, 4/4: 16 beats, bars starting every 2 s
FAKE_ACTIVATIONS = BeatActivations(
    *network_output([0.5 + 0.5 * i for i in range(16)], [0.5 + 2.0 * i for i in range(4)], 9.0),
    fps=FRAMES_PER_SECOND,
    model="fake",
)
FAKE_BEATS = analyze_activations(FAKE_ACTIVATIONS)


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
    """Stands in for BeatThisTracker: no network, instant result."""

    def __init__(self) -> None:
        self.model = "fake"
        self.analyzed: list[Path] = []
        self.error: str | None = None
        """When set, activations() raises BeatTrackingError with this message."""
        self.release = threading.Event()
        """activations() waits for this event; set by default so it finishes at once."""
        self.release.set()

    def activations(self, media_path: Path) -> BeatActivations:
        self.analyzed.append(media_path)
        self.release.wait(timeout=10)
        if self.error:
            raise BeatTrackingError(self.error)
        return FAKE_ACTIVATIONS


FAKE_STEM_NAMES = ("drums", "bass", "vocals", "other")
FAKE_FLAC = b"fLaC" + bytes(100)


class FakeStemSeparator:
    """Stands in for DemucsSeparator: no model, instant result."""

    def __init__(self) -> None:
        self.model = "fake"
        self.separated: list[Path] = []
        self.error: str | None = None
        """When set, separate() raises StemSeparationError with this message."""
        self.release = threading.Event()
        """separate() waits for this event after reporting half done; set by default."""
        self.release.set()
        self.started = threading.Event()
        """Set when separate() has reported half done."""
        self.stopped = 0

    def separate(
        self, media_path: Path, out_dir: Path, on_progress: StemProgressCallback
    ) -> StemSet:
        self.separated.append(media_path)
        (out_dir / f"{FAKE_STEM_NAMES[0]}.flac").write_bytes(FAKE_FLAC)
        on_progress(0.5)
        self.started.set()
        self.release.wait(timeout=10)
        if self.error:
            raise StemSeparationError(self.error)
        for name in FAKE_STEM_NAMES[1:]:
            (out_dir / f"{name}.flac").write_bytes(FAKE_FLAC)
        return StemSet(
            model=self.model,
            sample_rate=44100,
            duration=19,
            stems=[StemInfo(name=n, file=f"{n}.flac", rms=0.1) for n in FAKE_STEM_NAMES],
        )

    def stop(self) -> None:
        self.stopped += 1
        self.release.set()
        self.error = self.error or "Separation was stopped"


class FakeChordDetector:
    """Stands in for LibrosaChordDetector: C and G alternating every 4 beats."""

    method = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, list[Path], list[float]]] = []
        self.error: str | None = None
        """When set, detect() raises ChordDetectionError with this message."""

    def detect(self, media_path: Path, stem_paths, beats) -> list[Chord]:
        self.calls.append((media_path, list(stem_paths), list(beats)))
        if self.error:
            raise ChordDetectionError(self.error)
        bounds = [0.0, *beats[4::4], beats[-1] + 0.5]
        return [
            Chord(start=start, end=end, label="C:maj" if i % 2 == 0 else "G:maj")
            for i, (start, end) in enumerate(itertools.pairwise(bounds))
        ]


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


def wait_for_chords(client: TestClient, video_id: str, timeout: float = 5.0) -> dict:
    """Poll chord detection until it is no longer queued or running; return the final state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/api/library/{video_id}/chords").json()
        if state["status"] not in ("queued", "analyzing"):
            return state
        time.sleep(0.02)
    raise AssertionError(f"chord detection of {video_id} did not finish within {timeout} s")


def wait_for_stems(client: TestClient, video_id: str, timeout: float = 5.0) -> dict:
    """Poll stem separation until it is no longer queued or running; return the final state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/api/library/{video_id}/stems").json()
        if state["status"] not in ("queued", "analyzing"):
            return state
        time.sleep(0.02)
    raise AssertionError(f"stem separation of {video_id} did not finish within {timeout} s")
