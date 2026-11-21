"""Data models shared by the services and the HTTP API.

Naming: Python attributes are snake_case. The HTTP API speaks camelCase JSON
(the JavaScript convention); files on disk such as meta.json use snake_case,
because they are mainly read by Python code.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from music_trainer.video_ids import VIDEO_ID_PATTERN


class ApiModel(BaseModel):
    """Base model: immutable, camelCase field names in API JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)


class SearchResult(ApiModel):
    video_id: str
    title: str
    channel: str | None = None
    duration_seconds: float | None = None
    view_count: int | None = None
    thumbnail_url: str | None = None
    is_downloaded: bool = False


class VideoMetadata(ApiModel):
    """Everything stored about a downloaded video (its meta.json)."""

    video_id: str
    title: str
    channel: str | None = None
    duration_seconds: float | None = None
    upload_date: date | None = None
    view_count: int | None = None
    description: str | None = None
    source_url: str
    media_file: str
    """File name of the video inside the video's folder."""
    thumbnail_file: str | None = None
    downloaded_at: datetime | None = None


class LibraryVideo(ApiModel):
    """A downloaded video as the API returns it."""

    video_id: str
    title: str
    channel: str | None = None
    duration_seconds: float | None = None
    upload_date: date | None = None
    view_count: int | None = None
    description: str | None = None
    source_url: str
    downloaded_at: datetime | None = None
    media_url: str
    thumbnail_url: str | None = None


class DownloadStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    """Downloaded; ffmpeg is merging the video and audio streams."""
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_active(self) -> bool:
        return self in {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PROCESSING,
        }


class DownloadJob(ApiModel):
    video_id: str
    status: DownloadStatus
    progress: float = Field(ge=0.0, le=1.0)
    title: str | None = None
    error: str | None = None


class DownloadRequest(ApiModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    title: str | None = Field(default=None, max_length=500)
    """Title from the search result, shown while the download runs."""
