from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from tests.fakes import FakeBeatTracker, FakeYouTubeClient


@pytest.fixture
def fake_youtube() -> FakeYouTubeClient:
    return FakeYouTubeClient()


@pytest.fixture
def fake_beat_tracker() -> FakeBeatTracker:
    return FakeBeatTracker()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", frontend_dist_dir=tmp_path / "no-frontend")


@pytest.fixture
def client(
    settings: Settings, fake_youtube: FakeYouTubeClient, fake_beat_tracker: FakeBeatTracker
) -> Iterator[TestClient]:
    app = create_app(settings, youtube=fake_youtube, beat_tracker=fake_beat_tracker)
    with TestClient(app) as test_client:
        yield test_client
