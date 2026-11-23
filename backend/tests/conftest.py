from collections.abc import Iterator
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
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
    return Settings(
        data_dir=tmp_path / "data",
        frontend_dist_dir=tmp_path / "no-frontend",
        separate_stems_after_download=False,  # the tests start separations themselves
    )


@pytest.fixture
def library_dir(settings: Settings) -> Path:
    return settings.library_dir


# argon2's defaults take ~50 ms per hash on purpose; the tests need no protection
FAST_HASHER = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
PASSWORD = "correct horse battery"


@pytest.fixture
def app(
    settings: Settings,
    fake_youtube: FakeYouTubeClient,
    fake_beat_tracker: FakeBeatTracker,
    fake_stem_separator: FakeStemSeparator,
    fake_chord_detector: FakeChordDetector,
) -> FastAPI:
    return create_app(
        settings,
        youtube=fake_youtube,
        beat_tracker=fake_beat_tracker,
        stem_separator=fake_stem_separator,
        chord_detector=fake_chord_detector,
        password_hasher=FAST_HASHER,
    )


def register(client: TestClient, username: str, password: str = PASSWORD) -> dict:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def guest_client(app: FastAPI) -> Iterator[TestClient]:
    """A browser nobody is logged in on; runs the app's startup and shutdown."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(guest_client: TestClient, app: FastAPI) -> TestClient:
    """A browser logged in to the account "alice" (most tests need an account)."""
    test_client = TestClient(app)  # its own cookies; the app runs in guest_client's context
    register(test_client, "alice")
    return test_client
