"""HTTP API, end to end with a fake YouTube client."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_trainer.config import Settings
from tests.conftest import register
from tests.fakes import FAKE_MEDIA, OTHER_VIDEO_ID, VIDEO_ID, FakeYouTubeClient, wait_for_download
from tests.test_audio import read_wav, requires_ffmpeg, write_sine_wav


def download(client: TestClient, video_id: str = VIDEO_ID) -> dict:
    response = client.post("/api/downloads", json={"videoId": video_id, "title": "From search"})
    assert response.status_code == 202
    return wait_for_download(client, video_id)


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


class TestSearch:
    def test_returns_camel_case_results(self, client: TestClient) -> None:
        response = client.get("/api/search", params={"q": "zoo", "limit": 1})
        assert response.status_code == 200
        assert response.json() == [
            {
                "videoId": VIDEO_ID,
                "title": "Me at the zoo",
                "channel": "jawed",
                "durationSeconds": 19.0,
                "viewCount": None,
                "thumbnailUrl": None,
                "isDownloaded": False,
                "inLibrary": False,
            }
        ]

    def test_marks_downloaded_videos(self, client: TestClient) -> None:
        download(client)
        flags = {r["videoId"]: r["isDownloaded"] for r in client.get("/api/search?q=x").json()}
        assert flags == {VIDEO_ID: True, OTHER_VIDEO_ID: False}

    def test_marks_songs_in_my_library(self, client: TestClient, app: FastAPI) -> None:
        download(client)
        other = TestClient(app)
        register(other, "bob")
        for who, in_library in ((client, True), (other, False), (TestClient(app), False)):
            result = next(r for r in who.get("/api/search?q=x").json() if r["videoId"] == VIDEO_ID)
            assert (result["isDownloaded"], result["inLibrary"]) == (True, in_library)

    def test_trims_query(self, client: TestClient, fake_youtube: FakeYouTubeClient) -> None:
        client.get("/api/search", params={"q": "  bass lines  "})
        assert fake_youtube.queries == ["bass lines"]

    def test_rejects_empty_query(self, client: TestClient) -> None:
        assert client.get("/api/search", params={"q": ""}).status_code == 422

    def test_youtube_failure_is_bad_gateway(
        self, client: TestClient, fake_youtube: FakeYouTubeClient
    ) -> None:
        fake_youtube.error = "network down"
        response = client.get("/api/search", params={"q": "x"})
        assert response.status_code == 502
        assert "network down" in response.json()["detail"]


class TestDownloads:
    def test_download_adds_video_to_library(self, client: TestClient) -> None:
        job = download(client)
        assert job == {
            "videoId": VIDEO_ID,
            "status": "completed",
            "progress": 1.0,
            "title": f"Video {VIDEO_ID}",
            "error": None,
        }
        assert [v["videoId"] for v in client.get("/api/me/library").json()] == [VIDEO_ID]

    def test_running_download_reports_progress(
        self, client: TestClient, fake_youtube: FakeYouTubeClient
    ) -> None:
        fake_youtube.release_download.clear()
        client.post("/api/downloads", json={"videoId": VIDEO_ID})
        try:
            job = client.get(f"/api/downloads/{VIDEO_ID}").json()
            assert job["status"] in ("queued", "downloading")
            # starting again while running returns the same job instead of a second download
            again = client.post("/api/downloads", json={"videoId": VIDEO_ID}).json()
            assert again["status"] in ("queued", "downloading")
            assert len(client.get("/api/downloads").json()) == 1
        finally:
            fake_youtube.release_download.set()
        assert wait_for_download(client, VIDEO_ID)["status"] == "completed"

    def test_failed_download_reports_error_and_can_be_retried(
        self, client: TestClient, fake_youtube: FakeYouTubeClient
    ) -> None:
        fake_youtube.error = "Video unavailable"
        job = download(client)
        assert job["status"] == "failed"
        assert job["error"] == "Video unavailable"
        assert client.get("/api/me/library").json() == []

        fake_youtube.error = None
        assert download(client)["status"] == "completed"

    def test_already_downloaded_video_completes_at_once(self, client: TestClient) -> None:
        download(client)
        job = client.post("/api/downloads", json={"videoId": VIDEO_ID}).json()
        assert job["status"] == "completed"

    def test_unknown_download_is_404(self, client: TestClient) -> None:
        assert client.get(f"/api/downloads/{VIDEO_ID}").status_code == 404

    def test_invalid_video_id_is_rejected(self, client: TestClient) -> None:
        assert client.post("/api/downloads", json={"videoId": "../../x"}).status_code == 422
        assert client.get("/api/downloads/not-an-id").status_code == 422


class TestLibrary:
    def test_video_details_and_urls(self, client: TestClient) -> None:
        download(client)
        video = client.get(f"/api/library/{VIDEO_ID}").json()
        assert video["title"] == f"Video {VIDEO_ID}"
        assert video["mediaUrl"] == f"/api/library/{VIDEO_ID}/media"
        assert video["audioUrl"] == f"/api/library/{VIDEO_ID}/audio"
        assert video["thumbnailUrl"] == f"/api/library/{VIDEO_ID}/thumbnail"
        assert "mediaFile" not in video

    def test_media_supports_range_requests(self, client: TestClient) -> None:
        download(client)
        full = client.get(f"/api/library/{VIDEO_ID}/media")
        assert full.status_code == 200
        assert full.content == FAKE_MEDIA

        part = client.get(f"/api/library/{VIDEO_ID}/media", headers={"Range": "bytes=100-199"})
        assert part.status_code == 206
        assert part.content == FAKE_MEDIA[100:200]

    @requires_ffmpeg
    def test_audio_section(self, client: TestClient, settings: Settings) -> None:
        download(client)
        write_sine_wav(settings.library_dir / VIDEO_ID / "video.mp4", seconds=3.0)
        response = client.get(
            f"/api/library/{VIDEO_ID}/audio", params={"start": 1, "end": 2, "sampleRate": 44100}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        params, _ = read_wav(response.content)
        assert (params.nchannels, params.framerate, params.nframes) == (2, 44100, 44100)

    def test_audio_section_rejects_bad_ranges(self, client: TestClient) -> None:
        download(client)
        url = f"/api/library/{VIDEO_ID}/audio"
        assert client.get(url, params={"start": 2, "end": 1}).status_code == 422
        assert client.get(url, params={"start": -1, "end": 1}).status_code == 422
        assert client.get(url, params={"start": 0, "end": 901}).status_code == 422
        assert client.get(url, params={"start": 0}).status_code == 422
        assert client.get(url, params={"start": 0, "end": 1, "sampleRate": 1}).status_code == 422

    @requires_ffmpeg
    def test_unreadable_audio_is_server_error(self, client: TestClient) -> None:
        download(client)  # the fake media file is not audio
        response = client.get(f"/api/library/{VIDEO_ID}/audio", params={"start": 0, "end": 1})
        assert response.status_code == 500
        assert "could not read" in response.json()["detail"]

    def test_thumbnail(self, client: TestClient) -> None:
        download(client)
        assert client.get(f"/api/library/{VIDEO_ID}/thumbnail").content == b"jpeg"

    def test_delete(self, client: TestClient) -> None:
        download(client)
        assert client.delete(f"/api/me/library/{VIDEO_ID}").status_code == 204
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 404
        assert client.delete(f"/api/me/library/{VIDEO_ID}").status_code == 404

    def test_deleted_video_can_be_downloaded_again(self, client: TestClient) -> None:
        download(client)
        client.delete(f"/api/me/library/{VIDEO_ID}")
        assert client.get(f"/api/downloads/{VIDEO_ID}").status_code == 404
        assert download(client)["status"] == "completed"
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 200

    def test_saved_loops(self, client: TestClient) -> None:
        download(client)
        url = f"/api/me/library/{VIDEO_ID}/loops"
        assert client.get(url).json() == []
        loops = [
            {
                "id": "l1",
                "name": "Verse",
                "start": 10,
                "end": 20,
                "snapMode": "bar",
                "playbackRate": 0.8,
            },
            {"id": "l2", "name": "Solo", "start": 60.5, "end": 66.25},
        ]
        assert client.put(url, json=loops).status_code == 200
        stored = client.get(url).json()
        assert stored[0] == loops[0]
        assert stored[1] == {**loops[1], "snapMode": "off", "playbackRate": 1.0}

    def test_saved_loops_are_validated(self, client: TestClient) -> None:
        download(client)
        url = f"/api/me/library/{VIDEO_ID}/loops"
        loop = {"id": "l1", "name": "Verse", "start": 10, "end": 20}
        assert client.put(url, json=[loop, loop]).status_code == 422  # same id twice
        assert client.put(url, json=[{**loop, "end": 5}]).status_code == 422
        assert client.put(url, json=[{**loop, "playbackRate": 3}]).status_code == 422
        assert client.put(url, json=[{**loop, "snapMode": "half"}]).status_code == 422
        assert client.put(url, json=[{**loop, "id": "../x"}]).status_code == 422
        many = [{**loop, "id": f"l{i}"} for i in range(201)]
        assert client.put(url, json=many).status_code == 422

    def test_player_settings(self, client: TestClient) -> None:
        download(client)
        url = f"/api/me/library/{VIDEO_ID}/settings"
        defaults = client.get(url).json()
        assert defaults["volume"] == 1.0
        assert defaults["snapMode"] is None
        assert defaults["activeLoopId"] is None
        settings = {
            **defaults,
            "volume": 0.3,
            "muted": True,
            "playbackRate": 0.85,
            "snapMode": "beat",
            "position": 42.5,
            "loopStart": 10,
            "loopEnd": 20,
            "loopEnabled": True,
            "activeLoopId": "l1",
        }
        assert client.put(url, json=settings).json() == settings
        assert client.get(url).json() == settings
        assert client.put(url, json={**settings, "volume": 2}).status_code == 422

    def test_missing_video_is_404(self, client: TestClient) -> None:
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 404
        assert client.get(f"/api/library/{VIDEO_ID}/media").status_code == 404
        audio = client.get(f"/api/library/{VIDEO_ID}/audio", params={"start": 0, "end": 1})
        assert audio.status_code == 404
        assert client.get(f"/api/me/library/{VIDEO_ID}/loops").status_code == 404
        assert client.put(f"/api/me/library/{VIDEO_ID}/loops", json=[]).status_code == 404
        assert client.get(f"/api/me/library/{VIDEO_ID}/settings").status_code == 404
        assert client.put(f"/api/me/library/{VIDEO_ID}/settings", json={}).status_code == 404
