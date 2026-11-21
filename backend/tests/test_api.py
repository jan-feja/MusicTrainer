"""HTTP API, end to end with a fake YouTube client."""

from fastapi.testclient import TestClient

from tests.fakes import FAKE_MEDIA, OTHER_VIDEO_ID, VIDEO_ID, FakeYouTubeClient, wait_for_download


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
            }
        ]

    def test_marks_downloaded_videos(self, client: TestClient) -> None:
        download(client)
        flags = {r["videoId"]: r["isDownloaded"] for r in client.get("/api/search?q=x").json()}
        assert flags == {VIDEO_ID: True, OTHER_VIDEO_ID: False}

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
        assert [v["videoId"] for v in client.get("/api/library").json()] == [VIDEO_ID]

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
        assert client.get("/api/library").json() == []

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

    def test_thumbnail(self, client: TestClient) -> None:
        download(client)
        assert client.get(f"/api/library/{VIDEO_ID}/thumbnail").content == b"jpeg"

    def test_delete(self, client: TestClient) -> None:
        download(client)
        assert client.delete(f"/api/library/{VIDEO_ID}").status_code == 204
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 404
        assert client.delete(f"/api/library/{VIDEO_ID}").status_code == 404

    def test_deleted_video_can_be_downloaded_again(self, client: TestClient) -> None:
        download(client)
        client.delete(f"/api/library/{VIDEO_ID}")
        assert client.get(f"/api/downloads/{VIDEO_ID}").status_code == 404
        assert download(client)["status"] == "completed"
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 200

    def test_missing_video_is_404(self, client: TestClient) -> None:
        assert client.get(f"/api/library/{VIDEO_ID}").status_code == 404
        assert client.get(f"/api/library/{VIDEO_ID}/media").status_code == 404
