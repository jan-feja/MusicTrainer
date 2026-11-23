"""Beat detection: grid building, the background job and the API."""

import hashlib
import itertools
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_trainer.app import create_app
from music_trainer.config import Settings
from music_trainer.models import BeatAnalysis
from music_trainer.services.beats import (
    BeatThisTracker,
    BeatTrackingError,
    CheckpointSource,
    beat_analysis_from_times,
    ensure_checkpoint,
    estimate_bpm,
    most_common_bar_length,
)
from tests.fakes import (
    FAKE_BEATS,
    VIDEO_ID,
    FakeBeatTracker,
    FakeYouTubeClient,
    wait_for_beats,
    wait_for_download,
)


def download(client: TestClient, video_id: str = VIDEO_ID) -> None:
    client.post("/api/downloads", json={"videoId": video_id})
    assert wait_for_download(client, video_id)["status"] == "completed"


class TestBeatGrid:
    def test_tempo_and_bar_length(self) -> None:
        analysis = beat_analysis_from_times(
            [0.5 * i for i in range(1, 17)], [0.5, 2.5, 4.5, 6.5], analyzer="test"
        )
        assert analysis.bpm == 120.0
        assert analysis.beats_per_bar == 4
        assert analysis.analyzer == "test"

    def test_bar_starts_are_snapped_onto_beats(self) -> None:
        analysis = beat_analysis_from_times([1.0, 1.5, 2.0, 2.5], [1.004, 2.49], analyzer="t")
        assert analysis.downbeats == [1.0, 2.5]

    def test_times_are_sorted_and_rounded_to_milliseconds(self) -> None:
        analysis = beat_analysis_from_times([2.00049, 1.23456], [], analyzer="t")
        assert analysis.beats == [1.235, 2.0]
        assert analysis.downbeats == []
        assert analysis.beats_per_bar is None

    def test_empty_input(self) -> None:
        analysis = beat_analysis_from_times([], [1.0], analyzer="t")
        assert analysis.bpm is None
        assert analysis.beats == []
        assert analysis.downbeats == []

    def test_bpm_uses_the_median_gap(self) -> None:
        # one missed beat (a 1 s gap) must not drag the tempo down
        assert estimate_bpm([0.0, 0.5, 1.0, 2.0, 2.5, 3.0]) == 120.0
        assert estimate_bpm([1.0]) is None

    def test_most_common_bar_length(self) -> None:
        beats = [float(i) for i in range(20)]
        assert most_common_bar_length(beats, [0.0, 4.0, 8.0, 11.0, 15.0, 19.0]) == 4
        assert most_common_bar_length(beats, [0.0]) is None


class TestBeatsApi:
    def test_download_starts_beat_detection(self, client: TestClient, settings: Settings) -> None:
        download(client)
        state = wait_for_beats(client, VIDEO_ID)
        assert state["status"] == "completed"
        assert state["error"] is None
        assert state["analysis"] == {
            "bpm": 120.0,
            "beatsPerBar": 4,
            "beats": FAKE_BEATS.beats,
            "downbeats": FAKE_BEATS.downbeats,
            "analyzer": "fake+grid",
            "hints": {"beatsPerBar": None, "tempoBpm": None, "barStarts": [], "steadyTempo": False},
        }
        assert len(FAKE_BEATS.beats) == 16
        assert FAKE_BEATS.downbeats == [0.5, 2.5, 4.5, 6.5]
        assert (settings.library_dir / VIDEO_ID / "analysis.json").is_file()
        assert (settings.library_dir / VIDEO_ID / "beat_activations.npz").is_file()

    def test_detection_can_be_started_by_hand(
        self, tmp_path: Path, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        settings = Settings(
            data_dir=tmp_path / "data",
            frontend_dist_dir=tmp_path / "none",
            analyze_beats_after_download=False,
        )
        app = create_app(settings, youtube=FakeYouTubeClient(), beat_tracker=fake_beat_tracker)
        with TestClient(app) as client:
            download(client)
            assert client.get(f"/api/library/{VIDEO_ID}/beats").json()["status"] == "not_started"
            assert client.post(f"/api/library/{VIDEO_ID}/beats").status_code == 202
            assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"

    def test_running_detection_is_not_started_twice(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        fake_beat_tracker.release.clear()
        download(client)
        try:
            state = client.post(f"/api/library/{VIDEO_ID}/beats").json()
            assert state["status"] in ("queued", "analyzing")
            assert state["analysis"] is None
        finally:
            fake_beat_tracker.release.set()
        assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"
        assert len(fake_beat_tracker.analyzed) == 1

    def test_finished_detection_is_reused_unless_forced(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        assert client.post(f"/api/library/{VIDEO_ID}/beats").json()["status"] == "completed"
        assert len(fake_beat_tracker.analyzed) == 1

        client.post(f"/api/library/{VIDEO_ID}/beats", params={"force": True})
        assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"
        assert len(fake_beat_tracker.analyzed) == 2

    def test_hints_decode_again_without_the_network(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        response = client.post(f"/api/library/{VIDEO_ID}/beats", json={"beatsPerBar": 3})
        assert response.status_code == 202
        analysis = wait_for_beats(client, VIDEO_ID)["analysis"]
        assert analysis["beatsPerBar"] == 3
        assert analysis["hints"]["beatsPerBar"] == 3
        assert analysis["downbeats"] == analysis["beats"][::3]
        assert len(fake_beat_tracker.analyzed) == 1  # the stored network output was reused

        client.post(f"/api/library/{VIDEO_ID}/beats", json={"tempoBpm": 240})
        analysis = wait_for_beats(client, VIDEO_ID)["analysis"]
        assert analysis["bpm"] == pytest.approx(240, abs=8)
        assert analysis["hints"]["tempoBpm"] == 240

    def test_bar_starts_move_the_bars_without_decoding_again(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        beats = wait_for_beats(client, VIDEO_ID)["analysis"]["beats"]
        # "a bar starts on the 6th beat": from there on, bars are counted from it
        hints = {"beatsPerBar": None, "tempoBpm": None, "barStarts": [beats[5] + 0.01]}
        client.post(f"/api/library/{VIDEO_ID}/beats", json=hints)
        analysis = wait_for_beats(client, VIDEO_ID)["analysis"]
        # the one-beat bar this would leave (beat 4 to 5) joins the bar before: 5 beats
        assert analysis["downbeats"] == [beats[0], beats[5], beats[9], beats[13]]
        assert analysis["hints"]["barStarts"] == [beats[5] + 0.01]
        assert analysis["beatsPerBar"] == 4
        assert len(fake_beat_tracker.analyzed) == 1

        client.post(f"/api/library/{VIDEO_ID}/beats", json={**hints, "barStarts": []})
        assert wait_for_beats(client, VIDEO_ID)["analysis"]["downbeats"] == FAKE_BEATS.downbeats

    def test_steady_tempo_spaces_the_beats_evenly(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        client.post(f"/api/library/{VIDEO_ID}/beats", json={"steadyTempo": True})
        analysis = wait_for_beats(client, VIDEO_ID)["analysis"]
        assert analysis["hints"]["steadyTempo"] is True
        gaps = {round(b - a, 3) for a, b in itertools.pairwise(analysis["beats"])}
        assert gaps <= {0.499, 0.5, 0.501}  # rounded to ms
        assert len(fake_beat_tracker.analyzed) == 1

    def test_running_the_network_again_keeps_the_hints(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        client.post(f"/api/library/{VIDEO_ID}/beats", json={"beatsPerBar": 3})
        wait_for_beats(client, VIDEO_ID)
        client.post(f"/api/library/{VIDEO_ID}/beats", params={"force": True})
        analysis = wait_for_beats(client, VIDEO_ID)["analysis"]
        assert analysis["hints"]["beatsPerBar"] == 3
        assert len(fake_beat_tracker.analyzed) == 2

    def test_output_of_another_network_is_not_reused(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        fake_beat_tracker.model = "fake-v2"
        client.post(f"/api/library/{VIDEO_ID}/beats", json={"beatsPerBar": 4})
        wait_for_beats(client, VIDEO_ID)
        assert len(fake_beat_tracker.analyzed) == 2

    def test_invalid_hints_are_rejected(self, client: TestClient) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        for hints in ({"beatsPerBar": 1}, {"tempoBpm": 1000}, {"barStarts": [-1]}):
            response = client.post(f"/api/library/{VIDEO_ID}/beats", json=hints)
            assert response.status_code == 422, hints

    def test_grids_of_the_old_method_are_detected_again(
        self, client: TestClient, settings: Settings, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        old = BeatAnalysis(
            bpm=75.0, beats_per_bar=4, beats=[1.0], downbeats=[1.0], analyzer="beat_this:final0"
        )
        (settings.library_dir / VIDEO_ID / "analysis.json").write_text(old.model_dump_json())
        assert client.get(f"/api/library/{VIDEO_ID}/beats").json()["status"] == "not_started"
        client.post(f"/api/library/{VIDEO_ID}/beats")
        assert wait_for_beats(client, VIDEO_ID)["analysis"]["analyzer"] == "fake+grid"

    def test_failure_is_reported_and_can_be_retried(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        fake_beat_tracker.error = "model download failed"
        download(client)
        state = wait_for_beats(client, VIDEO_ID)
        assert state["status"] == "failed"
        assert state["error"] == "model download failed"

        fake_beat_tracker.error = None
        client.post(f"/api/library/{VIDEO_ID}/beats")
        assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"

    def test_deleting_the_video_removes_its_beats(
        self, client: TestClient, fake_beat_tracker: FakeBeatTracker
    ) -> None:
        download(client)
        wait_for_beats(client, VIDEO_ID)
        client.delete(f"/api/me/library/{VIDEO_ID}")
        assert client.get(f"/api/library/{VIDEO_ID}/beats").status_code == 404

        download(client)  # downloading again detects again
        assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"
        assert len(fake_beat_tracker.analyzed) == 2

    def test_unknown_or_invalid_video(self, client: TestClient) -> None:
        assert client.get(f"/api/library/{VIDEO_ID}/beats").status_code == 404
        assert client.post(f"/api/library/{VIDEO_ID}/beats").status_code == 404
        assert client.get("/api/library/not-an-id/beats").status_code == 422


def test_several_beat_models_are_named_together() -> None:
    tracker = BeatThisTracker("final0, final1,final2", Path("models"))
    assert tracker.model == "beat_this:final0+final1+final2"
    with pytest.raises(ValueError):
        BeatThisTracker(" , ", Path("models"))


class TestCheckpointDownload:
    def make_source(self, tmp_path: Path, content: bytes, sha256: str | None) -> CheckpointSource:
        source_file = tmp_path / "remote.ckpt"
        source_file.write_bytes(content)
        return CheckpointSource(source_file.as_uri(), sha256)

    def test_downloads_and_verifies(self, tmp_path: Path) -> None:
        content = b"model weights"
        source = self.make_source(tmp_path, content, hashlib.sha256(content).hexdigest())
        target = tmp_path / "models" / "model.ckpt"
        assert ensure_checkpoint(source, target) == target
        assert target.read_bytes() == content

    def test_rejects_corrupt_download(self, tmp_path: Path) -> None:
        source = self.make_source(tmp_path, b"tampered", hashlib.sha256(b"original").hexdigest())
        target = tmp_path / "models" / "model.ckpt"
        with pytest.raises(BeatTrackingError, match="corrupt"):
            ensure_checkpoint(source, target)
        assert not target.exists()
        assert not list(target.parent.iterdir())  # no partial file left behind

    def test_unreachable_source_explains_manual_download(self, tmp_path: Path) -> None:
        source = CheckpointSource((tmp_path / "missing.ckpt").as_uri(), None)
        target = tmp_path / "models" / "model.ckpt"
        with pytest.raises(BeatTrackingError, match="by hand"):
            ensure_checkpoint(source, target)

    def test_existing_file_is_not_downloaded_again(self, tmp_path: Path) -> None:
        target = tmp_path / "model.ckpt"
        target.write_bytes(b"already here")
        source = CheckpointSource("https://invalid.invalid/model.ckpt", "0" * 64)
        assert ensure_checkpoint(source, target).read_bytes() == b"already here"
