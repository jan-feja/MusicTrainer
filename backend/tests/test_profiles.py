"""Profiles: settings, privacy, following, starred songs, practice history and the feed."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_trainer.db import Database
from music_trainer.services.accounts import Accounts
from music_trainer.services.practice_history import PracticeHistory
from music_trainer.services.profiles import Profiles
from tests.conftest import PASSWORD, register
from tests.fakes import OTHER_VIDEO_ID, VIDEO_ID, wait_for_download


def download(client: TestClient, video_id: str = VIDEO_ID) -> None:
    client.post("/api/downloads", json={"videoId": video_id})
    assert wait_for_download(client, video_id)["status"] == "completed"


def practice(client: TestClient, seconds: int, video_id: str = VIDEO_ID) -> None:
    response = client.post("/api/me/practice", json={"videoId": video_id, "seconds": seconds})
    assert response.status_code == 204, response.text


def make_private(client: TestClient) -> None:
    client.put("/api/me/profile", json={"description": "", "isPrivate": True})


@pytest.fixture
def bob(app: FastAPI, client: TestClient) -> TestClient:
    """A second account; `client` is alice."""
    other = TestClient(app)
    register(other, "bob")
    return other


class TestProfile:
    def test_profile_and_settings(self, client: TestClient, guest_client: TestClient) -> None:
        settings = {"description": "  Bass player  ", "isPrivate": False}
        assert client.put("/api/me/profile", json=settings).json() == {
            "description": "Bass player",
            "isPrivate": False,
        }
        profile = guest_client.get("/api/users/ALICE").json()  # any case
        assert profile["username"] == "alice"
        assert profile["description"] == "Bass player"
        assert profile["followState"] == "none"
        assert profile["canView"] is True
        assert profile["libraryCount"] == 0
        assert profile["practiceSeconds"] == 0
        assert client.get("/api/users/alice").json()["followState"] == "self"

    def test_unknown_user_and_bad_settings(self, client: TestClient) -> None:
        assert client.get("/api/users/nobody").status_code == 404
        long = {"description": "x" * 301, "isPrivate": False}
        assert client.put("/api/me/profile", json=long).status_code == 422

    def test_settings_need_login(self, guest_client: TestClient) -> None:
        assert guest_client.get("/api/me/profile").status_code == 401
        assert guest_client.put("/api/users/alice/follow").status_code == 401


class TestStars:
    def test_star_a_song(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        download(client, OTHER_VIDEO_ID)
        url = f"/api/me/library/{VIDEO_ID}"
        assert client.get(url).json()["starred"] is False
        assert client.put(f"{url}/star", json={"starred": True}).status_code == 204
        assert client.get(url).json()["starred"] is True
        mine = {v["videoId"]: v["starred"] for v in client.get("/api/me/library").json()}
        assert mine == {VIDEO_ID: True, OTHER_VIDEO_ID: False}
        starred = guest_client.get("/api/users/alice/starred").json()
        assert [video["videoId"] for video in starred] == [VIDEO_ID]

        client.put(f"{url}/star", json={"starred": False})
        assert guest_client.get("/api/users/alice/starred").json() == []

    def test_only_songs_in_the_library(self, client: TestClient, bob: TestClient) -> None:
        download(client)
        response = bob.put(f"/api/me/library/{VIDEO_ID}/star", json={"starred": True})
        assert response.status_code == 404

    def test_profile_library(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        download(client, OTHER_VIDEO_ID)
        first = guest_client.get("/api/users/alice/library", params={"limit": 1}).json()
        assert [video["videoId"] for video in first["videos"]] == [OTHER_VIDEO_ID]
        assert first["total"] == 2


class TestFollowing:
    def test_follow_a_public_profile(self, client: TestClient, bob: TestClient) -> None:
        assert bob.put("/api/users/alice/follow").json() == "following"
        assert bob.put("/api/users/alice/follow").json() == "following"  # again: no change
        alice = bob.get("/api/users/alice").json()
        assert (alice["followState"], alice["followers"]) == ("following", 1)
        assert bob.get("/api/users/bob").json()["following"] == 1
        followers = client.get("/api/users/alice/followers").json()
        assert [user["username"] for user in followers] == ["bob"]
        assert [u["username"] for u in client.get("/api/users/bob/following").json()] == ["alice"]

        assert bob.delete("/api/users/alice/follow").status_code == 204
        assert client.get("/api/users/alice").json()["followers"] == 0

    def test_cannot_follow_yourself(self, client: TestClient) -> None:
        assert client.put("/api/users/alice/follow").status_code == 422

    def test_private_profile(
        self, client: TestClient, bob: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        make_private(client)
        for viewer in (bob, guest_client):
            profile = viewer.get("/api/users/alice").json()
            assert profile["canView"] is False
            assert profile["libraryCount"] is None and profile["practiceSeconds"] is None
            for part in ("starred", "library", "history", "followers", "following"):
                assert viewer.get(f"/api/users/alice/{part}").status_code == 403, part
        assert client.get("/api/users/alice/library").status_code == 200  # the owner sees all

        assert bob.put("/api/users/alice/follow").json() == "requested"
        assert notifications(client)[0][:2] == ("follow_request", "bob")
        assert bob.get("/api/users/alice/library").status_code == 403

        assert client.put("/api/me/followers/bob").status_code == 204
        assert bob.get("/api/users/alice").json()["followState"] == "following"
        assert bob.get("/api/users/alice/library").status_code == 200

        assert client.delete("/api/me/followers/bob").status_code == 204  # removed again
        assert bob.get("/api/users/alice").json()["followState"] == "none"

    def test_declining_and_going_public(self, client: TestClient, bob: TestClient) -> None:
        make_private(client)
        bob.put("/api/users/alice/follow")
        client.delete("/api/me/followers/bob")
        assert notifications(client) == []
        assert client.put("/api/me/followers/bob").status_code == 404

        bob.put("/api/users/alice/follow")
        client.put("/api/me/profile", json={"description": "", "isPrivate": False})
        assert bob.get("/api/users/alice").json()["followState"] == "following"

    def test_deleting_an_account_drops_its_follows(
        self, client: TestClient, bob: TestClient
    ) -> None:
        bob.put("/api/users/alice/follow")
        bob.request("DELETE", "/api/auth/account", json={"password": PASSWORD})
        assert client.get("/api/users/alice").json()["followers"] == 0


def notifications(client: TestClient) -> list[tuple[str, str, bool]]:
    items = client.get("/api/me/notifications").json()["items"]
    return [(item["kind"], item["username"], item["unread"]) for item in items]


class TestNotifications:
    def test_new_followers_and_requests(
        self, client: TestClient, bob: TestClient, app: FastAPI
    ) -> None:
        carol = TestClient(app)
        register(carol, "carol")
        assert client.get("/api/me/notifications").json() == {"items": [], "unread": 0}
        bob.put("/api/users/alice/follow")
        make_private(client)
        carol.put("/api/users/alice/follow")
        # the request waiting for an answer comes first
        assert notifications(client) == [
            ("follow_request", "carol", True),
            ("new_follower", "bob", True),
        ]
        assert client.get("/api/me/notifications").json()["unread"] == 2
        first = client.get("/api/me/notifications").json()["items"][1]
        assert first["followState"] == "none"  # alice does not follow bob back

        assert client.post("/api/me/notifications/seen").status_code == 204
        assert notifications(client) == [
            ("follow_request", "carol", False),
            ("new_follower", "bob", False),
        ]
        assert client.get("/api/me/notifications").json()["unread"] == 0

        client.put("/api/me/followers/carol")
        # carol now follows alice (as of her request), and hears that alice accepted
        assert [kind for kind, _, _ in notifications(client)] == ["new_follower", "new_follower"]
        assert notifications(carol) == [("request_accepted", "alice", True)]

    def test_taking_a_follow_back_removes_its_notification(
        self, client: TestClient, bob: TestClient
    ) -> None:
        bob.put("/api/users/alice/follow")
        bob.delete("/api/users/alice/follow")
        assert notifications(client) == []

    def test_needs_login(self, guest_client: TestClient) -> None:
        assert guest_client.get("/api/me/notifications").status_code == 401
        assert guest_client.post("/api/me/notifications/seen").status_code == 401


class TestHistory:
    def test_a_day_of_practice_is_one_entry(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        practice(client, 20)
        # under 30 s (a song opened and left) is not shown yet
        assert client.get("/api/users/alice/history").json() == []
        practice(client, 40)
        history = guest_client.get("/api/users/alice/history").json()
        assert len(history) == 1
        assert history[0]["videoId"] == VIDEO_ID
        assert history[0]["title"] == f"Video {VIDEO_ID}"
        assert history[0]["seconds"] == 60
        assert guest_client.get("/api/users/alice").json()["practiceSeconds"] == 60

    def test_reports_are_checked(self, client: TestClient, bob: TestClient) -> None:
        download(client)
        assert (
            bob.post("/api/me/practice", json={"videoId": VIDEO_ID, "seconds": 10}).status_code
            == 404
        )
        for seconds in (0, 601):
            body = {"videoId": VIDEO_ID, "seconds": seconds}
            assert client.post("/api/me/practice", json=body).status_code == 422

    def test_days_and_pages(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "db.sqlite")
        now = [datetime(2026, 1, 1, 23, 0, tzinfo=UTC)]
        history = PracticeHistory(db, clock=lambda: now[0])
        profiles = Profiles(db)
        user = Accounts(db, timedelta(days=1)).register("carol", PASSWORD)
        history.record(user.id, VIDEO_ID, "Song", 60)
        now[0] += timedelta(hours=2)  # the next day
        history.record(user.id, VIDEO_ID, "Song", 45)
        entries = history.history(user.id, limit=10)
        assert [(e.day.isoformat(), e.seconds) for e in entries] == [
            ("2026-01-02", 45),
            ("2026-01-01", 60),
        ]
        older = history.history(user.id, limit=10, before=entries[0].last_at)
        assert [e.seconds for e in older] == [60]
        assert profiles.find("CAROL") is not None


class TestFeed:
    def test_everyone_and_following(
        self, client: TestClient, bob: TestClient, guest_client: TestClient, app: FastAPI
    ) -> None:
        carol = TestClient(app)
        register(carol, "carol")
        for user in (client, bob, carol):
            download(user)
            practice(user, 60)
        make_private(carol)

        everyone = guest_client.get("/api/feed").json()
        assert sorted(entry["username"] for entry in everyone) == ["alice", "bob"]
        assert everyone[0]["title"] == f"Video {VIDEO_ID}"

        bob.put("/api/users/carol/follow")  # a request: not yet
        bob.put("/api/users/alice/follow")
        following = bob.get("/api/feed", params={"scope": "following"}).json()
        assert [entry["username"] for entry in following] == ["alice"]
        carol.put("/api/me/followers/bob")
        following = bob.get("/api/feed", params={"scope": "following"}).json()
        assert sorted(entry["username"] for entry in following) == ["alice", "carol"]

        assert guest_client.get("/api/feed", params={"scope": "following"}).status_code == 401
        assert len(guest_client.get("/api/feed", params={"limit": 1}).json()) == 1


def save_presets(client: TestClient, *names: str, video_id: str = VIDEO_ID) -> None:
    presets = [{"id": name.lower(), "name": name} for name in names]
    response = client.put(f"/api/me/library/{video_id}/presets", json=presets)
    assert response.status_code == 200, response.text


class TestPresetsOfFollowed:
    def test_presets_of_the_users_one_follows(
        self, client: TestClient, bob: TestClient, app: FastAPI
    ) -> None:
        carol = TestClient(app)
        register(carol, "carol")
        for user in (client, bob, carol):
            download(user)
        save_presets(bob, "Verse", "Chorus")
        save_presets(carol, "Solo")
        url = f"/api/me/library/{VIDEO_ID}/followed-presets"
        assert client.get(url).json() == []

        client.put("/api/users/bob/follow")
        make_private(carol)
        client.put("/api/users/carol/follow")  # only a request
        found = client.get(url).json()
        assert [(f["username"], [p["name"] for p in f["presets"]]) for f in found] == [
            ("bob", ["Verse", "Chorus"])
        ]
        carol.put("/api/me/followers/alice")
        assert [f["username"] for f in client.get(url).json()] == ["bob", "carol"]

    def test_needs_login(self, guest_client: TestClient) -> None:
        url = f"/api/me/library/{VIDEO_ID}/followed-presets"
        assert guest_client.get(url).status_code == 401


def activity(entries: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [(e["kind"], e["seconds"], e["preset"]) for e in entries]


class TestPresetsInHistory:
    def test_a_new_preset_is_an_entry_of_its_own(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        practice(client, 40)
        save_presets(client, "Verse")
        history = guest_client.get("/api/users/alice/history").json()
        assert activity(history) == [("preset", 0, "Verse"), ("practice", 40, None)]
        feed = guest_client.get("/api/feed").json()
        assert (feed[0]["username"], feed[0]["preset"]) == ("alice", "Verse")
        assert feed[0]["title"] == f"Video {VIDEO_ID}"

        save_presets(client, "Verse", "Chorus")
        presets = [{"id": "verse", "name": "Intro"}, {"id": "chorus", "name": "Chorus"}]
        client.put(f"/api/me/library/{VIDEO_ID}/presets", json=presets)  # renamed
        history = guest_client.get("/api/users/alice/history").json()
        assert sorted(e["preset"] for e in history if e["kind"] == "preset") == ["Chorus", "Intro"]
        assert len(guest_client.get("/api/users/alice/history", params={"limit": 2}).json()) == 2

    def test_a_deleted_preset_leaves_the_history(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        save_presets(client, "Verse")
        save_presets(client)
        assert guest_client.get("/api/users/alice/history").json() == []
        assert guest_client.get("/api/feed").json() == []


class TestHomePage:
    def test_practiced_today(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        assert client.get("/api/me/practice/today").json() == {"seconds": 0}
        practice(client, 40)
        practice(client, 20)
        assert client.get("/api/me/practice/today").json() == {"seconds": 60}
        assert guest_client.get("/api/me/practice/today").status_code == 401

    def test_today_leaves_out_other_days(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "db.sqlite")
        now = [datetime(2026, 1, 1, 23, 0, tzinfo=UTC)]
        history = PracticeHistory(db, clock=lambda: now[0])
        user = Accounts(db, timedelta(days=1)).register("carol", PASSWORD)
        history.record(user.id, VIDEO_ID, "Song", 60)
        now[0] += timedelta(hours=2)  # the next day
        history.record(user.id, OTHER_VIDEO_ID, "Other", 45)
        assert history.today_seconds(user.id) == 45

    def test_people_to_discover(
        self, app: FastAPI, client: TestClient, bob: TestClient, guest_client: TestClient
    ) -> None:
        carol = TestClient(app)
        register(carol, "carol")
        dave = TestClient(app)
        register(dave, "dave")
        make_private(dave)

        def people(viewer: TestClient, query: str = "") -> set[str]:
            response = viewer.get(f"/api/users{query}")
            assert response.status_code == 200, response.text
            return {user["username"] for user in response.json()}

        assert people(guest_client) == {"alice", "bob", "carol"}  # not the private dave
        assert people(client) == {"bob", "carol"}  # not alice herself
        client.put("/api/users/bob/follow")
        assert people(client) == {"carol"}  # nor whom she follows
        assert len(people(guest_client, "?count=1")) == 1

    def test_people_followed(
        self, app: FastAPI, client: TestClient, bob: TestClient, guest_client: TestClient
    ) -> None:
        carol = TestClient(app)
        register(carol, "carol")
        make_private(carol)

        def followed(query: str = "") -> set[str]:
            response = client.get(f"/api/me/following/random{query}")
            assert response.status_code == 200, response.text
            return {user["username"] for user in response.json()}

        assert followed() == set()
        client.put("/api/users/bob/follow")
        client.put("/api/users/carol/follow")  # only a request
        assert followed() == {"bob"}
        carol.put("/api/me/followers/alice")  # accepted
        assert followed() == {"bob", "carol"}
        assert len(followed("?count=1")) == 1
        assert guest_client.get("/api/me/following/random").status_code == 401
