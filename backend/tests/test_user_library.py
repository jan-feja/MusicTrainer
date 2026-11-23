"""Users' own libraries, guests, and deleting songs nobody has."""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from tests.conftest import FAST_HASHER, register
from tests.fakes import (
    OTHER_VIDEO_ID,
    VIDEO_ID,
    FakeBeatTracker,
    FakeChordDetector,
    FakeStemSeparator,
    FakeYouTubeClient,
    wait_for_beats,
    wait_for_download,
)

PRESET = {
    "id": "l1",
    "name": "Verse",
    "start": 10,
    "end": 20,
    "snapMode": "off",
    "playbackRate": 1,
    "mixer": None,
    "metronome": None,
}


def download(client: TestClient, video_id: str = VIDEO_ID) -> None:
    client.post("/api/downloads", json={"videoId": video_id})
    assert wait_for_download(client, video_id)["status"] == "completed"


def my_library(client: TestClient) -> list[str]:
    return [video["videoId"] for video in client.get("/api/me/library").json()]


@pytest.fixture
def bob(app: FastAPI, client: TestClient) -> TestClient:
    """A second account; `client` is alice."""
    other = TestClient(app)
    register(other, "bob")
    return other


class TestOwnLibrary:
    def test_downloading_adds_to_the_downloaders_library_only(
        self, client: TestClient, bob: TestClient
    ) -> None:
        download(client)
        assert my_library(client) == [VIDEO_ID]
        assert my_library(bob) == []
        assert bob.get(f"/api/me/library/{VIDEO_ID}/presets").status_code == 404
        # the song itself is open to everyone who knows it
        assert bob.get(f"/api/library/{VIDEO_ID}").status_code == 200

    def test_newest_first(self, client: TestClient) -> None:
        download(client)
        download(client, OTHER_VIDEO_ID)
        assert my_library(client) == [OTHER_VIDEO_ID, VIDEO_ID]

    def test_adding_a_song_from_the_server(self, client: TestClient, bob: TestClient) -> None:
        download(client)
        assert bob.put(f"/api/me/library/{VIDEO_ID}").status_code == 204
        assert bob.put(f"/api/me/library/{VIDEO_ID}").status_code == 204  # again: no change
        assert my_library(bob) == [VIDEO_ID]
        assert bob.put(f"/api/me/library/{OTHER_VIDEO_ID}").status_code == 404

    def test_presets_and_settings_are_per_user(self, client: TestClient, bob: TestClient) -> None:
        download(client)
        bob.put(f"/api/me/library/{VIDEO_ID}")
        client.put(f"/api/me/library/{VIDEO_ID}/presets", json=[PRESET])
        client.put(f"/api/me/library/{VIDEO_ID}/settings", json={"volume": 0.25})

        assert bob.get(f"/api/me/library/{VIDEO_ID}/presets").json() == []
        assert bob.get(f"/api/me/library/{VIDEO_ID}/settings").json()["volume"] == 1.0
        assert client.get(f"/api/me/library/{VIDEO_ID}/presets").json() == [PRESET]
        assert client.get(f"/api/me/library/{VIDEO_ID}/settings").json()["volume"] == 0.25

    def test_settings_keep_the_mixer(self, client: TestClient) -> None:
        download(client)
        url = f"/api/me/library/{VIDEO_ID}/settings"
        mixer = {"enabled": True, "volumes": {"bass": 0.5}, "muted": ["vocals"], "solo": []}
        client.put(url, json={"mixer": mixer})
        assert client.get(url).json()["mixer"] == mixer

    def test_needs_login(self, guest_client: TestClient) -> None:
        assert guest_client.get("/api/me/library").status_code == 401
        assert guest_client.put(f"/api/me/library/{VIDEO_ID}").status_code == 401
        assert guest_client.get(f"/api/me/library/{VIDEO_ID}/presets").status_code == 401


class TestRemovingSongs:
    def test_song_stays_while_someone_has_it(
        self, client: TestClient, bob: TestClient, library_dir: Path
    ) -> None:
        download(client)
        bob.put(f"/api/me/library/{VIDEO_ID}")

        assert client.delete(f"/api/me/library/{VIDEO_ID}").status_code == 204
        assert my_library(client) == []
        assert (library_dir / VIDEO_ID).is_dir()

        assert bob.delete(f"/api/me/library/{VIDEO_ID}").status_code == 204
        assert not (library_dir / VIDEO_ID).exists()
        assert bob.delete(f"/api/me/library/{VIDEO_ID}").status_code == 404

    def test_removing_drops_the_presets(self, client: TestClient) -> None:
        download(client)
        client.put(f"/api/me/library/{VIDEO_ID}/presets", json=[PRESET])
        client.delete(f"/api/me/library/{VIDEO_ID}")
        download(client)
        assert client.get(f"/api/me/library/{VIDEO_ID}/presets").json() == []

    def test_song_removed_while_downloading_is_deleted_when_done(
        self, client: TestClient, fake_youtube: FakeYouTubeClient, library_dir: Path
    ) -> None:
        fake_youtube.release_download.clear()
        client.post("/api/downloads", json={"videoId": VIDEO_ID})
        client.delete(f"/api/me/library/{VIDEO_ID}")
        fake_youtube.release_download.set()
        # once done, the cleanup deletes the song and forgets the job (the GET turns 404)
        deadline = time.monotonic() + 5
        while client.get(f"/api/downloads/{VIDEO_ID}").status_code == 200:
            assert time.monotonic() < deadline, "the finished song was not deleted"
            time.sleep(0.02)
        assert not (library_dir / VIDEO_ID).exists()

    def test_song_a_guest_used_recently_is_kept(
        self, client: TestClient, guest_client: TestClient, library_dir: Path
    ) -> None:
        download(client)
        guest_client.get(f"/api/library/{VIDEO_ID}")  # a guest opens it
        client.delete(f"/api/me/library/{VIDEO_ID}")
        assert (library_dir / VIDEO_ID).is_dir()


@pytest.fixture
def make_app(
    settings: Settings,
    fake_youtube: FakeYouTubeClient,
    fake_beat_tracker: FakeBeatTracker,
    fake_stem_separator: FakeStemSeparator,
    fake_chord_detector: FakeChordDetector,
) -> Iterator:
    """Start the app (again) on the same data folder, e.g. with other settings."""

    def make(**changes: object) -> FastAPI:
        return create_app(
            settings.model_copy(update=changes),
            youtube=fake_youtube,
            beat_tracker=fake_beat_tracker,
            stem_separator=fake_stem_separator,
            chord_detector=fake_chord_detector,
            password_hasher=FAST_HASHER,
        )

    yield make


class TestGuests:
    def test_guest_downloads_are_kept_for_a_while(self, make_app, library_dir: Path) -> None:
        with TestClient(make_app()) as guest:
            download(guest)
        with TestClient(make_app()):  # starting up sweeps
            assert (library_dir / VIDEO_ID).is_dir()
        with TestClient(make_app(guest_song_days=0)):
            assert not (library_dir / VIDEO_ID).exists()

    def test_songs_nobody_has_are_deleted_at_startup(
        self, make_app, settings: Settings, library_dir: Path
    ) -> None:
        with TestClient(make_app()) as guest:
            download(guest)
        settings.database_path.unlink()  # as for the songs from before there were accounts
        with TestClient(make_app()):
            assert not (library_dir / VIDEO_ID).exists()

    def test_guests_cannot_redo_shared_analysis(self, guest_client: TestClient) -> None:
        download(guest_client)
        assert wait_for_beats(guest_client, VIDEO_ID)["status"] == "completed"
        base = f"/api/library/{VIDEO_ID}"
        forced = guest_client.post(f"{base}/beats?force=true")
        assert forced.status_code == 401
        assert "Log in" in forced.json()["detail"]
        assert guest_client.post(f"{base}/stems?force=true").status_code == 401
        assert guest_client.post(f"{base}/chords?force=true").status_code == 401
        assert guest_client.post(f"{base}/beats").status_code == 202  # no change: allowed

    def test_beat_grid_fixes_are_each_users_own(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        url = f"/api/library/{VIDEO_ID}/beats/grid"
        # anyone (guests too) gets their own grid; the detected one does not change
        assert guest_client.post(url, json={"beatsPerBar": 3}).json()["beatsPerBar"] == 3
        assert client.post(url, json={"beatsPerBar": 2}).json()["beatsPerBar"] == 2
        assert wait_for_beats(client, VIDEO_ID)["analysis"]["beatsPerBar"] == 4

    def test_download_list_shows_only_my_songs(
        self, client: TestClient, bob: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        download(bob, OTHER_VIDEO_ID)
        assert [job["videoId"] for job in client.get("/api/downloads").json()] == [VIDEO_ID]
        assert [j["videoId"] for j in bob.get("/api/downloads").json()] == [OTHER_VIDEO_ID]
        assert guest_client.get("/api/downloads").json() == []
        guest_jobs = guest_client.get("/api/downloads", params={"ids": [OTHER_VIDEO_ID]}).json()
        assert [job["videoId"] for job in guest_jobs] == [OTHER_VIDEO_ID]


class TestImport:
    def test_guest_library_moves_into_the_account(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(guest_client)
        download(guest_client, OTHER_VIDEO_ID)
        client.put(f"/api/me/library/{OTHER_VIDEO_ID}")
        mine = {**PRESET, "name": "Mine"}
        client.put(f"/api/me/library/{OTHER_VIDEO_ID}/presets", json=[mine])

        entries = [
            {"videoId": VIDEO_ID, "presets": [PRESET], "settings": {"volume": 0.5}},
            {"videoId": OTHER_VIDEO_ID, "presets": [PRESET]},
            {"videoId": "9bZkp7q19f0"},  # cleaned up meanwhile: skipped
        ]
        assert client.post("/api/me/library/import", json=entries).status_code == 204

        assert sorted(my_library(client)) == sorted([VIDEO_ID, OTHER_VIDEO_ID])
        assert client.get(f"/api/me/library/{VIDEO_ID}/presets").json() == [PRESET]
        assert client.get(f"/api/me/library/{VIDEO_ID}/settings").json()["volume"] == 0.5
        # the account's own presets win
        assert client.get(f"/api/me/library/{OTHER_VIDEO_ID}/presets").json() == [mine]


class TestRandomSongs:
    """The home page: a few songs of the user's library and a few others on the server."""

    def ids(self, client: TestClient, url: str) -> set[str]:
        response = client.get(url)
        assert response.status_code == 200, response.text
        return {video["videoId"] for video in response.json()}

    def test_own_songs_and_the_others(self, client: TestClient, bob: TestClient) -> None:
        download(client)
        download(bob, OTHER_VIDEO_ID)
        assert self.ids(client, "/api/me/library/random") == {VIDEO_ID}
        assert self.ids(client, "/api/library/random") == {OTHER_VIDEO_ID}
        assert self.ids(bob, "/api/library/random") == {VIDEO_ID}

    def test_a_guest_sees_every_song(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        download(client, OTHER_VIDEO_ID)
        assert self.ids(guest_client, "/api/library/random") == {VIDEO_ID, OTHER_VIDEO_ID}
        assert len(self.ids(guest_client, "/api/library/random?count=1")) == 1
        assert len(self.ids(client, "/api/me/library/random?count=1")) == 1
        assert guest_client.get("/api/me/library/random").status_code == 401
