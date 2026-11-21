"""Talks to the real YouTube. Not run by default: `pytest -m network`.

Uses MUSIC_TRAINER_DENO_PATH / MUSIC_TRAINER_FFMPEG_PATH like the app does.
"""

from pathlib import Path

import pytest

from music_trainer.config import Settings
from music_trainer.services.youtube import DownloadProgress, YtDlpClient
from music_trainer.video_ids import is_valid_video_id

pytestmark = pytest.mark.network

SHORT_VIDEO_ID = "jNQXAC9IVRw"  # "Me at the zoo", 19 s


@pytest.fixture
def youtube() -> YtDlpClient:
    settings = Settings()
    return YtDlpClient(
        max_video_height=360, deno_path=settings.deno_path, ffmpeg_path=settings.ffmpeg_path
    )


def test_search(youtube: YtDlpClient) -> None:
    results = youtube.search("bass guitar lesson", limit=5)
    assert 1 <= len(results) <= 5
    assert all(is_valid_video_id(r.video_id) and r.title for r in results)


def test_search_by_link(youtube: YtDlpClient) -> None:
    results = youtube.search(f"https://youtu.be/{SHORT_VIDEO_ID}", limit=5)
    assert [r.video_id for r in results] == [SHORT_VIDEO_ID]


def test_download(youtube: YtDlpClient, tmp_path: Path) -> None:
    reports: list[DownloadProgress] = []
    metadata = youtube.download(SHORT_VIDEO_ID, tmp_path, reports.append)
    assert metadata.title
    assert (tmp_path / metadata.media_file).stat().st_size > 10_000
    assert reports
    assert reports[-1].fraction == pytest.approx(1.0)
