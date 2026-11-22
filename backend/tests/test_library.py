from pathlib import Path

import numpy as np
import pytest

from music_trainer.models import BeatAnalysis, PlayerSettings, SavedLoop, VideoMetadata
from music_trainer.services.beat_decoding import BeatActivations
from music_trainer.services.library import Library, VideoNotInLibraryError
from music_trainer.video_ids import InvalidVideoIdError, watch_url

VIDEO_ID = "jNQXAC9IVRw"


def add_video(library: Library, video_id: str = VIDEO_ID, title: str = "Title") -> VideoMetadata:
    staging = library.create_staging_dir(video_id)
    (staging / "video.mp4").write_bytes(b"media")
    metadata = VideoMetadata(
        video_id=video_id, title=title, source_url=watch_url(video_id), media_file="video.mp4"
    )
    return library.commit(video_id, metadata)


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return Library(tmp_path / "library")


def test_commit_moves_download_into_library(library: Library) -> None:
    stored = add_video(library)

    assert stored.downloaded_at is not None
    assert library.contains(VIDEO_ID)
    assert library.get_video(VIDEO_ID) == stored
    assert library.media_path(VIDEO_ID) == library.root / VIDEO_ID / "video.mp4"
    assert library.thumbnail_path(VIDEO_ID) is None
    assert not (library.root / Library.STAGING_DIR / VIDEO_ID).exists()


def test_list_videos_newest_first(library: Library) -> None:
    add_video(library, VIDEO_ID, "first")
    add_video(library, "dQw4w9WgXcQ", "second")
    assert [v.title for v in library.list_videos()] == ["second", "first"]


def test_list_videos_skips_broken_and_staging_folders(library: Library) -> None:
    add_video(library)
    (library.root / "aaaaaaaaaaa").mkdir()
    (library.root / "aaaaaaaaaaa" / "meta.json").write_text("{not json")
    library.create_staging_dir("dQw4w9WgXcQ")
    assert [v.video_id for v in library.list_videos()] == [VIDEO_ID]


def test_commit_replaces_existing_video(library: Library) -> None:
    add_video(library, title="old")
    add_video(library, title="new")
    assert library.get_video(VIDEO_ID).title == "new"


def test_delete_video(library: Library) -> None:
    add_video(library)
    assert library.delete_video(VIDEO_ID) is True
    assert not library.contains(VIDEO_ID)
    assert library.delete_video(VIDEO_ID) is False


def test_media_path_never_leaves_video_folder(library: Library) -> None:
    add_video(library)
    meta_file = library.root / VIDEO_ID / Library.METADATA_FILE
    tampered = library.get_video(VIDEO_ID).model_copy(update={"media_file": "../../secret.txt"})
    meta_file.write_text(tampered.model_dump_json())
    assert library.media_path(VIDEO_ID) is None


def test_invalid_ids_are_rejected(library: Library) -> None:
    with pytest.raises(InvalidVideoIdError):
        library.get_video("../outside!")
    with pytest.raises(InvalidVideoIdError):
        library.create_staging_dir("..")


def test_clear_staging(library: Library) -> None:
    library.create_staging_dir(VIDEO_ID)
    library.clear_staging()
    assert not (library.root / Library.STAGING_DIR).exists()


def test_beat_analysis_roundtrip(library: Library) -> None:
    add_video(library)
    assert library.read_beat_analysis(VIDEO_ID) is None
    analysis = BeatAnalysis(
        bpm=120.0, beats_per_bar=4, beats=[0.5, 1.0], downbeats=[0.5], analyzer="test"
    )
    library.write_beat_analysis(VIDEO_ID, analysis)
    assert library.read_beat_analysis(VIDEO_ID) == analysis
    assert (library.root / VIDEO_ID / "analysis.json").is_file()
    assert not (library.root / VIDEO_ID / "analysis.json.part").exists()


def test_beat_analysis_needs_the_video(library: Library) -> None:
    analysis = BeatAnalysis(bpm=None, beats_per_bar=None, beats=[], downbeats=[], analyzer="t")
    with pytest.raises(VideoNotInLibraryError):
        library.write_beat_analysis(VIDEO_ID, analysis)


def test_beat_activations_roundtrip(library: Library) -> None:
    add_video(library)
    assert library.read_beat_activations(VIDEO_ID) is None
    beat = np.linspace(-8, 4, 500, dtype=np.float32)
    activations = BeatActivations(beat=beat, downbeat=-beat, fps=50.0, model="beat_this:final0")
    library.write_beat_activations(VIDEO_ID, activations)
    loaded = library.read_beat_activations(VIDEO_ID)
    assert loaded is not None
    assert loaded.model == "beat_this:final0"
    assert loaded.fps == 50.0
    assert np.allclose(loaded.beat, beat, atol=0.01)
    assert np.allclose(loaded.downbeat, -beat, atol=0.01)
    assert not (library.root / VIDEO_ID / "beat_activations.npz.part").exists()


def test_beat_activations_need_the_video(library: Library) -> None:
    activations = BeatActivations(beat=np.zeros(3), downbeat=np.zeros(3), fps=50.0, model="m")
    with pytest.raises(VideoNotInLibraryError):
        library.write_beat_activations(VIDEO_ID, activations)


def test_unreadable_beat_activations_are_ignored(library: Library) -> None:
    add_video(library)
    (library.root / VIDEO_ID / "beat_activations.npz").write_bytes(b"not a zip")
    assert library.read_beat_activations(VIDEO_ID) is None


def test_unreadable_beat_analysis_is_ignored(library: Library) -> None:
    add_video(library)
    (library.root / VIDEO_ID / "analysis.json").write_text("{broken")
    assert library.read_beat_analysis(VIDEO_ID) is None


def test_loops_roundtrip(library: Library) -> None:
    add_video(library)
    assert library.read_loops(VIDEO_ID) == []
    loops = [
        SavedLoop(id="a1", name="Verse", start=10.5, end=20.25, snap_mode="bar"),
        SavedLoop(id="b2", name="Solo", start=60, end=66.4, playback_rate=0.75),
    ]
    library.write_loops(VIDEO_ID, loops)
    assert library.read_loops(VIDEO_ID) == loops
    # files on disk use snake_case
    assert '"snap_mode": "bar"' in (library.root / VIDEO_ID / "loops.json").read_text()


def test_player_settings_roundtrip(library: Library) -> None:
    add_video(library)
    assert library.read_player_settings(VIDEO_ID) is None
    settings = PlayerSettings(
        volume=0.4, playback_rate=0.8, loop_start=3, loop_end=7, active_loop_id="a1"
    )
    library.write_player_settings(VIDEO_ID, settings)
    assert library.read_player_settings(VIDEO_ID) == settings


def test_loops_and_settings_need_the_video(library: Library) -> None:
    with pytest.raises(VideoNotInLibraryError):
        library.write_loops(VIDEO_ID, [])
    with pytest.raises(VideoNotInLibraryError):
        library.write_player_settings(VIDEO_ID, PlayerSettings())


def test_unreadable_loops_are_ignored(library: Library) -> None:
    add_video(library)
    (library.root / VIDEO_ID / "loops.json").write_text("[{broken")
    assert library.read_loops(VIDEO_ID) == []


def test_loop_must_end_after_it_starts() -> None:
    with pytest.raises(ValueError, match="end must be after start"):
        SavedLoop(id="x", name="Bad", start=5, end=5)
