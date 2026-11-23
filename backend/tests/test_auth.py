"""Accounts: registering, logging in and out, changing the password, deleting the account."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_trainer.db import Database
from music_trainer.services.accounts import Accounts
from tests.conftest import FAST_HASHER, PASSWORD, register
from tests.fakes import VIDEO_ID, wait_for_download


def login(client: TestClient, username: str, password: str = PASSWORD) -> int:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return response.status_code


class TestRegister:
    def test_registering_logs_in(self, guest_client: TestClient) -> None:
        assert guest_client.get("/api/auth/me").json() is None
        user = register(guest_client, "Alice")
        assert user["username"] == "Alice"
        assert guest_client.get("/api/auth/me").json() == user

    def test_usernames_are_unique_regardless_of_case(
        self, guest_client: TestClient, app: FastAPI
    ) -> None:
        register(guest_client, "alice")
        other = TestClient(app)
        response = other.post(
            "/api/auth/register", json={"username": "ALICE", "password": PASSWORD}
        )
        assert response.status_code == 409
        assert "taken" in response.json()["detail"]

    def test_username_and_password_are_checked(self, guest_client: TestClient) -> None:
        for username, password in [
            ("al", PASSWORD),  # too short
            ("al ice", PASSWORD),
            ("a" * 31, PASSWORD),
            ("alice", "short"),
        ]:
            body = {"username": username, "password": password}
            assert guest_client.post("/api/auth/register", json=body).status_code == 422


class TestLogin:
    def test_login_and_logout(self, guest_client: TestClient, app: FastAPI) -> None:
        register(TestClient(app), "alice")
        assert login(guest_client, "ALICE") == 200  # any case
        assert guest_client.get("/api/auth/me").json()["username"] == "alice"

        assert guest_client.post("/api/auth/logout").status_code == 204
        assert guest_client.get("/api/auth/me").json() is None

    def test_wrong_password_or_unknown_user(self, guest_client: TestClient, app: FastAPI) -> None:
        register(TestClient(app), "alice")
        assert login(guest_client, "alice", "wrong password") == 401
        assert login(guest_client, "bob") == 401
        assert guest_client.get("/api/auth/me").json() is None

    def test_logged_out_session_cannot_be_reused(self, client: TestClient) -> None:
        token = client.cookies["music_trainer_session"]
        client.post("/api/auth/logout")
        client.cookies.set("music_trainer_session", token)
        assert client.get("/api/auth/me").json() is None

    def test_cookie_is_http_only(self, guest_client: TestClient) -> None:
        response = guest_client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}
        )
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=lax" in cookie


class TestChangePassword:
    def test_new_password_works_and_other_sessions_end(
        self, client: TestClient, app: FastAPI
    ) -> None:
        elsewhere = TestClient(app)
        assert login(elsewhere, "alice") == 200

        body = {"currentPassword": PASSWORD, "newPassword": "new password 1"}
        assert client.post("/api/auth/password", json=body).status_code == 204
        assert client.get("/api/auth/me").json()["username"] == "alice"  # this one stays
        assert elsewhere.get("/api/auth/me").json() is None

        assert login(TestClient(app), "alice") == 401
        assert login(TestClient(app), "alice", "new password 1") == 200

    def test_wrong_current_password(self, client: TestClient) -> None:
        body = {"currentPassword": "wrong", "newPassword": "new password 1"}
        assert client.post("/api/auth/password", json=body).status_code == 403

    def test_needs_login(self, guest_client: TestClient) -> None:
        body = {"currentPassword": PASSWORD, "newPassword": "new password 1"}
        assert guest_client.post("/api/auth/password", json=body).status_code == 401


class TestDeleteAccount:
    def test_deletes_the_account_and_its_songs(
        self, client: TestClient, app: FastAPI, library_dir: Path
    ) -> None:
        client.post("/api/downloads", json={"videoId": VIDEO_ID})
        wait_for_download(client, VIDEO_ID)
        assert (library_dir / VIDEO_ID).is_dir()

        wrong = client.request("DELETE", "/api/auth/account", json={"password": "wrong"})
        assert wrong.status_code == 403
        response = client.request("DELETE", "/api/auth/account", json={"password": PASSWORD})
        assert response.status_code == 204
        assert client.get("/api/auth/me").json() is None
        assert login(TestClient(app), "alice") == 401
        assert not (library_dir / VIDEO_ID).exists()  # nobody else had it
        register(TestClient(app), "alice")  # the name is free again


class TestSessions:
    def test_sessions_expire_and_are_extended_when_used(self, tmp_path: Path) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        accounts = Accounts(
            Database(tmp_path / "db.sqlite"), timedelta(days=30), lambda: now, FAST_HASHER
        )
        user = accounts.register("alice", PASSWORD)
        token = accounts.create_session(user.id)

        now += timedelta(days=20)
        assert accounts.user_for_token(token) == user  # extended to day 50
        now += timedelta(days=29)
        assert accounts.user_for_token(token) == user
        now += timedelta(days=31)
        assert accounts.user_for_token(token) is None
        assert accounts.user_for_token("made up") is None
