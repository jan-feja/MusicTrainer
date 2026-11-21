from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from tests.fakes import FakeYouTubeClient


@pytest.fixture
def fake_youtube() -> FakeYouTubeClient:
    return FakeYouTubeClient()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", frontend_dist_dir=tmp_path / "no-frontend")


@pytest.fixture
def client(settings: Settings, fake_youtube: FakeYouTubeClient) -> Iterator[TestClient]:
    with TestClient(create_app(settings, youtube=fake_youtube)) as test_client:
        yield test_client
