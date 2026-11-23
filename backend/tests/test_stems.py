"""Stem separation: the background job, its API and the stems on disk (with a fake separator)."""

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from music_trainer.services.stem_worker import PROGRESS_PREFIX, RESULT_PREFIX
from music_trainer.services.stems import DemucsSeparator, StemSeparationError
from tests.fakes import (
    FAKE_FLAC,
    FAKE_STEM_NAMES,
    OTHER_VIDEO_ID,
    VIDEO_ID,
    FakeBeatTracker,
    FakeStemSeparator,
    FakeYouTubeClient,
    wait_for_download,
    wait_for_stems,
)

STEMS_URL = f"/api/library/{VIDEO_ID}/stems"


def download(client: TestClient, video_id: str = VIDEO_ID) -> None:
    client.post("/api/downloads", json={"videoId": video_id})
    assert wait_for_download(client, video_id)["status"] == "completed"


class TestStemsApi:
    def test_not_separated_after_download(
        self, client: TestClient, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        assert client.get(STEMS_URL).json() == {
            "videoId": VIDEO_ID,
            "status": "not_started",
            "progress": None,
            "queuePosition": None,
            "stems": None,
            "error": None,
        }
        assert fake_stem_separator.separated == []

    def test_separate_and_fetch_a_stem(self, client: TestClient, settings: Settings) -> None:
        download(client)
        response = client.post(STEMS_URL)
        assert response.status_code == 202
        assert response.json()["status"] in ("queued", "analyzing", "completed")

        state = wait_for_stems(client, VIDEO_ID)
        assert state["status"] == "completed"
        assert state["progress"] is None  # a finished job reads its result from disk
        stems = state["stems"]
        assert [s["name"] for s in stems["stems"]] == list(FAKE_STEM_NAMES)
        assert stems["sampleRate"] == 44100

        stem = client.get(f"{STEMS_URL}/bass")
        assert stem.status_code == 200
        assert stem.headers["content-type"] == "audio/flac"
        assert stem.content == FAKE_FLAC

        folder = settings.library_dir / VIDEO_ID
        assert (folder / "stems" / "stems.json").is_file()
        assert not (folder / "stems.partial").exists()

    def test_running_separation_reports_progress_and_is_not_started_twice(
        self, client: TestClient, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        fake_stem_separator.release.clear()
        client.post(STEMS_URL)
        assert fake_stem_separator.started.wait(timeout=5)
        state = client.get(STEMS_URL).json()
        assert state["status"] == "analyzing"
        assert state["progress"] == 0.5
        assert state["stems"] is None
        assert client.post(STEMS_URL).json()["status"] == "analyzing"

        fake_stem_separator.release.set()
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"
        assert len(fake_stem_separator.separated) == 1

    def test_finished_stems_are_reused_unless_forced(
        self, client: TestClient, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        client.post(STEMS_URL)
        wait_for_stems(client, VIDEO_ID)
        assert client.post(STEMS_URL).json()["status"] == "completed"
        assert len(fake_stem_separator.separated) == 1

        client.post(STEMS_URL, params={"force": True})
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"
        assert len(fake_stem_separator.separated) == 2

    def test_failure_is_reported_and_can_be_retried(
        self, client: TestClient, settings: Settings, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        fake_stem_separator.error = "out of memory"
        client.post(STEMS_URL)
        state = wait_for_stems(client, VIDEO_ID)
        assert state["status"] == "failed"
        assert state["error"] == "out of memory"
        assert not (settings.library_dir / VIDEO_ID / "stems.partial").exists()
        assert client.get(f"{STEMS_URL}/drums").status_code == 404

        fake_stem_separator.error = None
        client.post(STEMS_URL)
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"

    def test_deleting_the_video_stops_the_separation(
        self, client: TestClient, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        fake_stem_separator.release.clear()
        client.post(STEMS_URL)
        assert fake_stem_separator.started.wait(timeout=5)

        assert client.delete(f"/api/library/{VIDEO_ID}").status_code == 204
        assert fake_stem_separator.stopped == 1
        assert client.get(STEMS_URL).status_code == 404

        download(client)  # downloading again starts from scratch
        assert client.get(STEMS_URL).json()["status"] == "not_started"

    def test_the_song_in_the_player_is_separated_next(
        self, client: TestClient, settings: Settings, fake_stem_separator: FakeStemSeparator
    ) -> None:
        third = "9bZkp7q19f0"
        for video_id in (VIDEO_ID, OTHER_VIDEO_ID, third):
            download(client, video_id)
        fake_stem_separator.release.clear()
        separation = client.app.state.services.stem_separation  # type: ignore[attr-defined]
        separation.start(VIDEO_ID)
        assert fake_stem_separator.started.wait(timeout=5)
        separation.start(OTHER_VIDEO_ID)  # as after a download: at the end of the queue
        separation.start(third)
        other = client.get(f"/api/library/{OTHER_VIDEO_ID}/stems").json()
        assert (other["status"], other["queuePosition"]) == ("queued", 1)

        # the player opens the third song: it moves to the front
        opened = client.post(f"/api/library/{third}/stems").json()
        assert (opened["status"], opened["queuePosition"]) == ("queued", 1)
        assert client.get(f"/api/library/{OTHER_VIDEO_ID}/stems").json()["queuePosition"] == 2

        fake_stem_separator.release.set()
        for video_id in (VIDEO_ID, OTHER_VIDEO_ID, third):
            assert wait_for_stems(client, video_id)["status"] == "completed"
        order = [path.parent.name for path in fake_stem_separator.separated]
        assert order == [VIDEO_ID, third, OTHER_VIDEO_ID]

    def test_deleting_a_queued_video_drops_it(
        self, client: TestClient, fake_stem_separator: FakeStemSeparator
    ) -> None:
        download(client)
        download(client, OTHER_VIDEO_ID)
        fake_stem_separator.release.clear()
        client.post(STEMS_URL)
        assert fake_stem_separator.started.wait(timeout=5)
        client.post(f"/api/library/{OTHER_VIDEO_ID}/stems")
        assert client.delete(f"/api/library/{OTHER_VIDEO_ID}").status_code == 204

        fake_stem_separator.release.set()
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"
        assert [path.parent.name for path in fake_stem_separator.separated] == [VIDEO_ID]

    def test_unknown_stem_video_or_name(self, client: TestClient) -> None:
        assert client.get(STEMS_URL).status_code == 404
        assert client.post(STEMS_URL).status_code == 404
        assert client.get(f"{STEMS_URL}/drums").status_code == 404
        download(client)
        assert client.get(f"{STEMS_URL}/drums").status_code == 404  # not separated yet
        assert client.get(f"{STEMS_URL}/..%2Fmeta.json").status_code in (404, 422)
        assert client.get(f"{STEMS_URL}/Drums").status_code == 422
        assert client.get("/api/library/not-an-id/stems").status_code == 422


def test_new_downloads_are_separated(
    settings: Settings,
    fake_youtube: FakeYouTubeClient,
    fake_beat_tracker: FakeBeatTracker,
    fake_stem_separator: FakeStemSeparator,
) -> None:
    assert Settings.model_fields["separate_stems_after_download"].default is True
    settings = settings.model_copy(update={"separate_stems_after_download": True})
    app = create_app(
        settings,
        youtube=fake_youtube,
        beat_tracker=fake_beat_tracker,
        stem_separator=fake_stem_separator,
    )
    with TestClient(app) as client:
        download(client)
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"


class TestStemsOnDisk:
    def write_stems(self, settings: Settings, stems: list[dict]) -> Path:
        folder = settings.library_dir / VIDEO_ID / "stems"
        folder.mkdir()
        stem_set = {"model": "fake", "sample_rate": 44100, "duration": 19, "stems": stems}
        (folder / "stems.json").write_text(json.dumps(stem_set))
        return folder

    def test_stems_with_a_missing_file_are_ignored(
        self, client: TestClient, settings: Settings
    ) -> None:
        download(client)
        folder = self.write_stems(
            settings,
            [
                {"name": "drums", "file": "drums.flac", "rms": 0.1},
                {"name": "bass", "file": "bass.flac", "rms": 0.1},
            ],
        )
        (folder / "drums.flac").write_bytes(FAKE_FLAC)
        assert client.get(STEMS_URL).json()["status"] == "not_started"

    def test_stem_files_must_be_inside_the_stems_folder(
        self, client: TestClient, settings: Settings
    ) -> None:
        download(client)
        self.write_stems(settings, [{"name": "drums", "file": "../video.mp4", "rms": 0.1}])
        assert client.get(STEMS_URL).json()["status"] == "not_started"
        assert client.get(f"{STEMS_URL}/drums").status_code == 404


class TestDemucsSeparator:
    """The child-process protocol, with a stand-in worker instead of Demucs."""

    def run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str) -> list[float]:
        """Separate with `script` standing in for the worker; returns the progress reported."""
        worker = tmp_path / "worker.py"
        worker.write_text(script)
        original_popen = subprocess.Popen

        def popen(command: list[str], **kwargs: object) -> subprocess.Popen[str]:
            # command is [python, "-m", "music_trainer.services.stem_worker", arguments...]
            return original_popen([command[0], str(worker), *command[3:]], **kwargs)

        monkeypatch.setattr("music_trainer.services.stems.subprocess.Popen", popen)
        separator = DemucsSeparator("htdemucs_6s", tmp_path / "models")
        progress: list[float] = []
        self.result = separator.separate(tmp_path / "song.mp4", tmp_path, progress.append)
        return progress

    def test_reads_progress_and_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = {"model": "demucs:htdemucs_6s", "sample_rate": 44100, "duration": 3, "stems": []}
        script = (
            "import sys\n"
            "print('some warning from torch', file=sys.stderr)\n"
            f"print('{PROGRESS_PREFIX}0.25')\n"
            f"print('{PROGRESS_PREFIX}0.75')\n"
            f"print('{RESULT_PREFIX}' + {json.dumps(json.dumps(result))})\n"
        )
        assert self.run(tmp_path, monkeypatch, script) == [0.25, 0.75]
        assert self.result.model == "demucs:htdemucs_6s"

    def test_failure_reports_the_last_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script = (
            "import sys\nprint('ffmpeg could not read song.mp4', file=sys.stderr)\nsys.exit(1)\n"
        )
        with pytest.raises(StemSeparationError, match=r"ffmpeg could not read song\.mp4"):
            self.run(tmp_path, monkeypatch, script)

    def test_missing_result_is_a_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(StemSeparationError, match="Separation failed: hello"):
            self.run(tmp_path, monkeypatch, "print('hello')\n")
