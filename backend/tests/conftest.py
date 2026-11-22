from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from tests.fakes import FakeBeatTracker, FakeChordDetector, FakeStemSeparator, FakeYouTubeClient


@pytest.fixture
def fake_youtube() -> FakeYouTubeClient:
    return FakeYouTubeClient()


@pytest.fixture
def fake_beat_tracker() -> FakeBeatTracker:
    return FakeBeatTracker()


@pytest.fixture
def fake_stem_separator() -> FakeStemSeparator:
    return FakeStemSeparator()


@pytest.fixture
def fake_chord_detector() -> FakeChordDetector:
    return FakeChordDetector()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", frontend_dist_dir=tmp_path / "no-frontend")


@pytest.fixture
def client(
    settings: Settings,
    fake_youtube: FakeYouTubeClient,
    fake_beat_tracker: FakeBeatTracker,
    fake_stem_separator: FakeStemSeparator,
    fake_chord_detector: FakeChordDetector,
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        youtube=fake_youtube,
        beat_tracker=fake_beat_tracker,
        stem_separator=fake_stem_separator,
        chord_detector=fake_chord_detector,
    )
    with TestClient(app) as test_client:
        yield test_client
