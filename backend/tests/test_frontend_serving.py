from pathlib import Path

from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from tests.fakes import FakeYouTubeClient


def make_client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    settings = Settings(data_dir=tmp_path / "data", frontend_dist_dir=dist)
    return TestClient(create_app(settings, youtube=FakeYouTubeClient()))


def test_serves_built_frontend(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/").text == "<html>app</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_client_side_routes_get_index_html(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/watch/jNQXAC9IVRw").text == "<html>app</html>"


def test_unknown_api_routes_stay_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/api/nope").status_code == 404


def test_paths_outside_dist_are_not_served(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret")
    client = make_client(tmp_path)
    assert "secret" not in client.get("/../secret.txt").text
