"""Data models shared by the services and the HTTP API.

Naming: Python attributes are snake_case. The HTTP API speaks camelCase JSON
(the JavaScript convention); files on disk such as meta.json use snake_case,
because they are mainly read by Python code.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

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


class BeatGridHints(ApiModel):
    """What the user knows about a song's beat grid; None leaves it to the detection."""

    beats_per_bar: int | None = Field(default=None, ge=2, le=12)
    """Every bar has this many beats."""
    tempo_bpm: float | None = Field(default=None, ge=30, le=300)
    """The tempo is near this; decides between e.g. 75 and 150 BPM."""
    bar_starts: list[Annotated[float, Field(ge=0)]] = Field(default_factory=list, max_length=500)
    """Times (s) where a bar starts; from each one on, bars are counted from there."""
    steady_tempo: bool = False
    """The song is played to a click: space all beats exactly evenly."""


class BeatAnalysis(ApiModel):
    """The beat grid of a song; stored as analysis.json in the video's folder."""

    bpm: float | None
    """Tempo from the median time between beats; None if too few beats were found."""
    beats_per_bar: int | None
    """Most common number of beats between bar starts (4 for most pop songs)."""
    beats: list[float]
    """Beat times in seconds, ascending."""
    downbeats: list[float]
    """Bar starts in seconds; each one is also in `beats`."""
    analyzer: str
    """Which method produced the grid, e.g. 'beat_this:final0+grid'."""
    hints: BeatGridHints = Field(default_factory=BeatGridHints)
    """The user's hints the grid was decoded with."""


class AnalysisStatus(StrEnum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_active(self) -> bool:
        return self in {AnalysisStatus.QUEUED, AnalysisStatus.ANALYZING}


class BeatTrackingState(ApiModel):
    """Where beat detection of a video stands, with the result once it is done."""

    video_id: str
    status: AnalysisStatus
    analysis: BeatAnalysis | None = None
    error: str | None = None
