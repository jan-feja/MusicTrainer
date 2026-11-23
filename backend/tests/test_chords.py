"""Chords: the detection maths, the real detector on a synthetic song, and the API."""

import numpy as np
from fastapi.testclient import TestClient

from music_trainer.config import Settings
from music_trainer.services.chords import (
    NO_CHORD,
    chord_templates,
    detect_chords,
    label_segments,
    merge_segments,
    segment_bounds,
    viterbi,
)
from tests.fakes import (
    FAKE_BEATS,
    VIDEO_ID,
    FakeChordDetector,
    FakeStemSeparator,
    wait_for_beats,
    wait_for_chords,
    wait_for_download,
    wait_for_stems,
)

CHORDS_URL = f"/api/library/{VIDEO_ID}/chords"
SAMPLE_RATE = 22050


def chroma_of(*pitch_classes: int) -> np.ndarray:
    row = np.zeros(12)
    row[list(pitch_classes)] = 1
    return row


class TestDetection:
    def test_templates_are_24_triads_and_no_chord(self) -> None:
        labels, templates = chord_templates()
        assert len(labels) == 25 and labels[-1] == NO_CHORD
        assert labels[0] == "C:maj" and labels[1] == "C:min" and labels[19] == "A:min"
        assert np.allclose(np.linalg.norm(templates[:24], axis=1), 1)

    def test_segments_run_from_beat_to_beat(self) -> None:
        assert segment_bounds([0.5, 1.0, 9.0], 2.0).tolist() == [0, 0.5, 1.0, 2.0]

    def test_one_odd_beat_does_not_make_a_new_chord(self) -> None:
        c_major, a_minor = chroma_of(0, 4, 7), chroma_of(9, 0, 4)
        beats = np.array([c_major] * 4 + [a_minor] + [c_major] * 3)
        loudness = np.ones(len(beats))
        assert set(label_segments(beats, loudness)) == {"C:maj"}
        # ... while a chord held for a few beats does
        beats = np.array([c_major] * 4 + [a_minor] * 4)
        assert label_segments(beats, loudness) == ["C:maj"] * 4 + ["A:min"] * 4

    def test_silence_is_no_chord(self) -> None:
        beats = np.array([chroma_of(0, 4, 7)] * 4)
        labels = label_segments(beats, np.array([1, 1, 0, 0]))
        assert labels == ["C:maj", "C:maj", NO_CHORD, NO_CHORD]

    def test_viterbi_follows_strong_evidence(self) -> None:
        log_emission = np.log(np.array([[0.9, 0.1], [0.9, 0.1], [0.01, 0.99], [0.01, 0.99]]))
        assert viterbi(log_emission, stay=0.8).tolist() == [0, 0, 1, 1]

    def test_neighbours_with_the_same_chord_merge(self) -> None:
        chords = merge_segments(np.array([0, 0.5, 1, 1.5]), ["C:maj", "C:maj", "G:maj"])
        assert [(c.start, c.end, c.label) for c in chords] == [
            (0, 1, "C:maj"),
            (1, 1.5, "G:maj"),
        ]

    def test_finds_a_played_progression_on_the_beats(self) -> None:
        def tone(midi: int, seconds: float) -> np.ndarray:
            t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
            envelope = np.minimum(1, t * 50) * np.exp(-t * 0.8)
            return np.sin(2 * np.pi * 440 * 2 ** ((midi - 69) / 12) * t) * envelope

        progression = [
            ("C:maj", [48, 60, 64, 67]),
            ("G:maj", [43, 59, 62, 67]),
            ("A:min", [45, 57, 60, 64]),
            ("F:maj", [41, 57, 60, 65]),
        ] * 2
        song = np.concatenate([sum(tone(m, 2.0) for m in notes) for _, notes in progression])
        beats = [0.5 * i for i in range(1, 32)]

        chords = detect_chords(song.astype(np.float32) * 0.2, SAMPLE_RATE, beats, False)

        assert [c.label for c in chords] == [label for label, _ in progression]
        assert [c.start for c in chords] == [2.0 * i for i in range(8)]


def download_with_beats(client: TestClient) -> None:
    client.post("/api/downloads", json={"videoId": VIDEO_ID})
    assert wait_for_download(client, VIDEO_ID)["status"] == "completed"
    assert wait_for_beats(client, VIDEO_ID)["status"] == "completed"


class TestChordsApi:
    def test_needs_the_beats_first(self, client: TestClient, settings: Settings) -> None:
        download_with_beats(client)
        (settings.library_dir / VIDEO_ID / "analysis.json").unlink()
        response = client.post(CHORDS_URL)
        assert response.status_code == 409
        assert "beats" in response.json()["detail"]

    def test_detect_and_reuse(
        self, client: TestClient, fake_chord_detector: FakeChordDetector
    ) -> None:
        download_with_beats(client)
        assert client.get(CHORDS_URL).json()["status"] == "not_started"
        assert client.post(CHORDS_URL).status_code == 202
        state = wait_for_chords(client, VIDEO_ID)
        assert state["status"] == "completed"
        analysis = state["analysis"]
        assert analysis["method"] == "fake"
        assert analysis["fromStems"] is False
        assert [c["label"] for c in analysis["chords"]][:2] == ["C:maj", "G:maj"]
        # on the beat grid, without the stems (none separated)
        _, stems, beats = fake_chord_detector.calls[0]
        assert stems == [] and beats == FAKE_BEATS.beats

        assert client.post(CHORDS_URL).json()["status"] == "completed"
        assert len(fake_chord_detector.calls) == 1
        client.post(CHORDS_URL, params={"force": True})
        wait_for_chords(client, VIDEO_ID)
        assert len(fake_chord_detector.calls) == 2

    def test_each_beat_grid_has_its_chords(
        self, client: TestClient, fake_chord_detector: FakeChordDetector
    ) -> None:
        download_with_beats(client)
        client.post(CHORDS_URL)
        detected = wait_for_chords(client, VIDEO_ID)
        # half the tempo: every other beat (a new meter alone keeps the beats and the chords)
        hints = {"beatsPerBar": None, "tempoBpm": 60, "barStarts": [], "steadyTempo": False}
        state = client.post(CHORDS_URL, json=hints).json()
        assert state["grid"] != detected["grid"]
        mine = wait_for_chords(client, VIDEO_ID, grid=state["grid"])
        assert mine["status"] == "completed"
        assert len(fake_chord_detector.calls[-1][2]) < len(FAKE_BEATS.beats)  # its own beats
        # the chords of the detected grid are still there for everyone else
        assert client.get(CHORDS_URL).json() == detected
        assert client.post(CHORDS_URL, json={"beatsPerBar": 3}).json() == detected
        assert len(fake_chord_detector.calls) == 2

    def test_stems_are_used_once_separated(
        self,
        client: TestClient,
        fake_chord_detector: FakeChordDetector,
        fake_stem_separator: FakeStemSeparator,
    ) -> None:
        download_with_beats(client)
        client.post(CHORDS_URL)
        wait_for_chords(client, VIDEO_ID)
        client.post(f"/api/library/{VIDEO_ID}/stems")
        assert wait_for_stems(client, VIDEO_ID)["status"] == "completed"
        # chords from the whole mix are detected again on the stems
        assert client.get(CHORDS_URL).json()["status"] == "not_started"
        client.post(CHORDS_URL)
        assert wait_for_chords(client, VIDEO_ID)["analysis"]["fromStems"] is True
        _, stems, _ = fake_chord_detector.calls[-1]
        # the pitched stems the fake separator makes: no drums, no vocals
        assert sorted(path.stem for path in stems) == ["bass", "other"]

    def test_failure_is_reported_and_can_be_retried(
        self, client: TestClient, fake_chord_detector: FakeChordDetector
    ) -> None:
        download_with_beats(client)
        fake_chord_detector.error = "no harmony"
        client.post(CHORDS_URL)
        state = wait_for_chords(client, VIDEO_ID)
        assert state["status"] == "failed" and state["error"] == "no harmony"
        fake_chord_detector.error = None
        client.post(CHORDS_URL)
        assert wait_for_chords(client, VIDEO_ID)["status"] == "completed"

    def test_unknown_or_invalid_video(self, client: TestClient) -> None:
        assert client.get(CHORDS_URL).status_code == 404
        assert client.post(CHORDS_URL).status_code == 404
        assert client.get("/api/library/not-an-id/chords").status_code == 422
        assert client.get(CHORDS_URL, params={"grid": "../x"}).status_code == 422
