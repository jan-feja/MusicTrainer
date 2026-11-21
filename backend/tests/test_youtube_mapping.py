"""Conversion of yt-dlp data into our models, and progress calculation."""

from datetime import date

import pytest

from music_trainer.services.youtube import (
    DownloadProgress,
    _ProgressTracker,
    clean_error_message,
    metadata_from_info,
    parse_upload_date,
    pick_thumbnail_url,
    search_result_from_entry,
)

# shape of an entry from `ytsearch` with extract_flat (trimmed)
SEARCH_ENTRY = {
    "_type": "url",
    "ie_key": "Youtube",
    "id": "jNQXAC9IVRw",
    "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "title": "Me at the zoo",
    "duration": 19.0,
    "channel": "jawed",
    "view_count": 380000000,
    "thumbnails": [
        {"url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hq720.jpg?a", "height": 202, "width": 360},
        {"url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hq720.jpg?b", "height": 404, "width": 720},
    ],
}


def test_search_result_from_entry() -> None:
    result = search_result_from_entry(SEARCH_ENTRY)
    assert result is not None
    assert result.video_id == "jNQXAC9IVRw"
    assert result.title == "Me at the zoo"
    assert result.channel == "jawed"
    assert result.duration_seconds == 19.0
    assert result.view_count == 380000000
    assert result.thumbnail_url == "https://i.ytimg.com/vi/jNQXAC9IVRw/hq720.jpg?a"
    assert result.is_downloaded is False


def test_search_result_fills_missing_fields() -> None:
    result = search_result_from_entry({"id": "jNQXAC9IVRw", "uploader": "someone"})
    assert result is not None
    assert result.title == "jNQXAC9IVRw"
    assert result.channel == "someone"
    assert result.thumbnail_url == "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg"


@pytest.mark.parametrize("entry", [{}, {"id": "UC4QobU6STFB0P71PMvOGN5A"}, {"id": None}])
def test_search_result_skips_non_videos(entry: dict) -> None:
    assert search_result_from_entry(entry) is None


def test_pick_thumbnail_url() -> None:
    assert pick_thumbnail_url([]) is None
    assert pick_thumbnail_url([{"url": "a"}]) == "a"
    assert (
        pick_thumbnail_url([{"url": "small", "width": 120}, {"url": "card", "width": 480}])
        == "card"
    )


def test_metadata_from_info() -> None:
    info = {
        "id": "jNQXAC9IVRw",
        "title": "Me at the zoo",
        "uploader": "jawed",
        "duration": 19,
        "upload_date": "20050424",
        "view_count": 5,
        "description": "The first video on YouTube.",
        "webpage_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    }
    metadata = metadata_from_info(info, media_file="video.mp4", thumbnail_file=None)
    assert metadata.channel == "jawed"
    assert metadata.upload_date == date(2005, 4, 24)
    assert metadata.media_file == "video.mp4"
    assert metadata.thumbnail_file is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("20240131", date(2024, 1, 31)), (None, None), ("", None), ("not-a-date", None)],
)
def test_parse_upload_date(value: str | None, expected: date | None) -> None:
    assert parse_upload_date(value) == expected


def test_clean_error_message() -> None:
    error = Exception(
        "ERROR: [youtube] d1PjsJL9UnM: Video unavailable. The account was terminated."
    )
    assert clean_error_message(error) == "Video unavailable. The account was terminated."
    assert (
        clean_error_message(Exception("Plain message: with colon")) == "Plain message: with colon"
    )


class TestProgressTracker:
    def make(self) -> tuple[_ProgressTracker, list[DownloadProgress]]:
        reports: list[DownloadProgress] = []
        return _ProgressTracker(reports.append), reports

    def test_weights_streams_by_size(self) -> None:
        tracker, reports = self.make()
        tracker.set_streams(
            [{"format_id": "v", "filesize": 900}, {"format_id": "a", "filesize": 100}]
        )
        video = {"info_dict": {"format_id": "v"}}
        audio = {"info_dict": {"format_id": "a"}}
        tracker.on_download_progress(
            {**video, "status": "downloading", "downloaded_bytes": 450, "total_bytes": 900}
        )
        tracker.on_download_progress({**video, "status": "finished"})
        tracker.on_download_progress(
            {**audio, "status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 100}
        )
        tracker.on_download_progress({**audio, "status": "finished"})
        assert [round(r.fraction, 3) for r in reports] == [0.45, 0.9, 0.95, 1.0]

    def test_equal_weights_when_sizes_unknown(self) -> None:
        tracker, reports = self.make()
        tracker.set_streams([{"format_id": "v"}, {"format_id": "a", "filesize": 100}])
        tracker.on_download_progress({"info_dict": {"format_id": "v"}, "status": "finished"})
        assert reports[-1].fraction == 0.5

    def test_merging_reports_processing(self) -> None:
        tracker, reports = self.make()
        tracker.on_postprocessor_progress({"status": "started", "postprocessor": "Merger"})
        tracker.on_postprocessor_progress({"status": "started", "postprocessor": "MoveFiles"})
        assert reports == [DownloadProgress("processing", 1.0)]
