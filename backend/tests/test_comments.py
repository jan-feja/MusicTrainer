"""Comments under songs: shown to everyone there, in the feed like other activity."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, register
from tests.fakes import OTHER_VIDEO_ID, VIDEO_ID
from tests.test_profiles import download, make_private

COMMENTS = f"/api/library/{VIDEO_ID}/comments"


def comment(client: TestClient, text: str, video_id: str = VIDEO_ID) -> dict:
    response = client.post(f"/api/library/{video_id}/comments", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()


def texts(client: TestClient, **params: object) -> list[str]:
    response = client.get(COMMENTS, params=params)
    assert response.status_code == 200, response.text
    return [item["text"] for item in response.json()]


class TestComments:
    def test_write_and_read(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        first = comment(client, "  Great groove  ")
        assert first["username"] == "alice"
        assert first["text"] == "Great groove"
        comment(client, "The bridge is hard")
        assert texts(guest_client) == ["The bridge is hard", "Great groove"]  # newest first
        assert texts(guest_client, limit=1) == ["The bridge is hard"]
        second = guest_client.get(COMMENTS).json()[0]
        assert texts(guest_client, before=second["createdAt"]) == ["Great groove"]
        assert guest_client.get(f"/api/library/{OTHER_VIDEO_ID}/comments").json() == []

    def test_needs_an_account_a_song_and_text(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        assert guest_client.post(COMMENTS, json={"text": "Hi"}).status_code == 401
        assert client.post(COMMENTS, json={"text": "   "}).status_code == 422
        assert client.post(COMMENTS, json={"text": "x" * 251}).status_code == 422
        missing = client.post(f"/api/library/{OTHER_VIDEO_ID}/comments", json={"text": "Hi"})
        assert missing.status_code == 404

    def test_only_the_author_deletes(self, app: FastAPI, client: TestClient) -> None:
        download(client)
        mine = comment(client, "Mine")
        bob = TestClient(app)
        register(bob, "bob")
        assert bob.delete(f"{COMMENTS}/{mine['id']}").status_code == 404
        other_song = f"/api/library/{OTHER_VIDEO_ID}/comments/{mine['id']}"
        assert client.delete(other_song).status_code == 404
        assert client.delete(f"{COMMENTS}/{mine['id']}").status_code == 204
        assert texts(client) == []
        assert client.get("/api/feed").json() == []

    def test_comments_in_the_feed(self, client: TestClient, guest_client: TestClient) -> None:
        download(client)
        comment(client, "In the feed")
        comment(client, "x" * 250)  # the longest
        feed = guest_client.get("/api/feed").json()
        assert [(entry["kind"], entry["username"]) for entry in feed] == [("comment", "alice")] * 2
        assert feed[1]["comment"] == "In the feed"
        assert feed[1]["title"] == f"Video {VIDEO_ID}"

    def test_private_profiles_comments_only_under_the_song(
        self, app: FastAPI, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        make_private(client)
        comment(client, "Under the song")
        assert texts(guest_client) == ["Under the song"]
        assert guest_client.get("/api/feed").json() == []  # not in the everyone feed

        bob = TestClient(app)
        register(bob, "bob")
        assert bob.get("/api/feed", params={"scope": "following"}).json() == []
        bob.put("/api/users/alice/follow")
        assert bob.get("/api/feed", params={"scope": "following"}).json() == []  # a request
        client.put("/api/me/followers/bob")
        following = bob.get("/api/feed", params={"scope": "following"}).json()
        assert [entry["comment"] for entry in following] == ["Under the song"]
        history = bob.get("/api/users/alice/history").json()
        assert [entry["kind"] for entry in history] == ["comment"]

    def test_deleting_the_account_deletes_its_comments(
        self, client: TestClient, guest_client: TestClient
    ) -> None:
        download(client)
        comment(client, "Bye")
        response = client.request("DELETE", "/api/auth/account", json={"password": PASSWORD})
        assert response.status_code == 204, response.text
        assert texts(guest_client) == []
