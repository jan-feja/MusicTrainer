"""Data models shared by the services and the HTTP API.

Naming: Python attributes are snake_case. The HTTP API speaks camelCase JSON
(the JavaScript convention); files on disk such as meta.json use snake_case,
because they are mainly read by Python code.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    """On the server (someone has it): adding it to a library is instant."""
    in_library: bool = False
    """In the logged-in user's library (a guest's library is in the browser: always False)."""


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
    audio_url: str
    """A section of the audio as WAV: `?start=&end=` in seconds (for gapless loops)."""
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


SnapMode = Literal["off", "beat", "bar"]
"""What loop points snap to: nothing, beats or bar starts."""

PRESET_ID_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"
MIN_PLAYBACK_RATE = 0.25
MAX_PLAYBACK_RATE = 2.0


class MetronomeSettings(ApiModel):
    enabled: bool = False
    volume: float = Field(default=0.3, ge=0, le=1)


class Preset(ApiModel):
    """A named way to practice a song: its loop, speed, stem mix and metronome.

    A user's presets of a song are a list of them. Choosing one sets the player
    that way; what a preset does not hold (no stem mix, say) is left as it is.
    """

    id: str = Field(pattern=PRESET_ID_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    start: float | None = Field(default=None, ge=0)
    """The loop, in seconds; None (with `end`): the whole song, no loop."""
    end: float | None = Field(default=None, gt=0)
    snap_mode: SnapMode = "off"
    """What the loop points snap to while the preset is played."""
    playback_rate: float = Field(default=1.0, ge=MIN_PLAYBACK_RATE, le=MAX_PLAYBACK_RATE)
    mixer: "MixerSettings | None" = None
    """The stem mix; None: the stems are left as they are."""
    metronome: MetronomeSettings | None = None
    """None: the metronome is left as it is."""

    @model_validator(mode="after")
    def _whole_loop(self) -> Self:
        if (self.start is None) != (self.end is None):
            raise ValueError("a loop needs both start and end")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class PlayerSettings(ApiModel):
    """How the player was left for a video (its player.json); restored when it is opened."""

    volume: float = Field(default=1.0, ge=0, le=1)
    muted: bool = False
    playback_rate: float = Field(default=1.0, ge=MIN_PLAYBACK_RATE, le=MAX_PLAYBACK_RATE)
    snap_mode: SnapMode | None = None
    """None: whatever the browser used last."""
    position: float = Field(default=0, ge=0)
    """Playback position in seconds."""
    loop_start: float | None = Field(default=None, ge=0)
    loop_end: float | None = Field(default=None, ge=0)
    loop_enabled: bool = False
    active_preset_id: str | None = Field(default=None, pattern=PRESET_ID_PATTERN)
    """The preset chosen last, if any."""
    mixer: "MixerSettings | None" = None
    """The stem mixer; None: stems were never turned on for this video."""
    metronome: MetronomeSettings | None = None
    grid_hints: BeatGridHints | None = None
    """The user's fixes of the beat grid; None: the detected grid as it is."""


STEM_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,30}$"
StemName = Annotated[str, Field(pattern=STEM_NAME_PATTERN)]


class StemInfo(ApiModel):
    """One separated instrument track of a song, as listed in its stems/stems.json."""

    name: StemName
    """'drums', 'bass', 'vocals', 'guitar', 'piano' or 'other' (whatever the model makes)."""
    file: str
    """File name inside stems/, a FLAC file."""
    rms: float = Field(ge=0)
    """Loudness (root mean square, 0-1); near 0: the instrument is not in the song."""


class StemSet(ApiModel):
    """The separated tracks of a song (its stems/stems.json).

    Every stem has the same sample rate and length and starts at time 0 of the video.
    """

    model: str
    """Which separator made them, e.g. 'demucs:htdemucs_6s'."""
    sample_rate: int = Field(gt=0)
    duration: float = Field(ge=0)
    """Seconds."""
    stems: list[StemInfo]


class StemSeparationState(ApiModel):
    """Where separating a video into stems stands, with the stems once it is done."""

    video_id: str
    status: AnalysisStatus
    progress: float | None = Field(default=None, ge=0, le=1)
    """Share of the song separated while the status is 'analyzing'; None if unknown."""
    queue_position: int | None = Field(default=None, ge=0)
    """While 'queued': how many songs are separated before this one."""
    stems: StemSet | None = None
    error: str | None = None


class Chord(ApiModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    label: str
    """Root and quality as in mir_eval, e.g. 'A:min', 'C:maj'; 'N' for no chord."""


class ChordAnalysis(ApiModel):
    """The chords of a song, changing only on beats (its chords.json)."""

    method: str
    """How they were found, e.g. 'chroma-templates+beats'."""
    chords: list[Chord]
    """In time order, without gaps between neighbours."""
    grid: str | None = None
    """The beat grid the chords were found on (see chords.beat_grid_key)."""
    from_stems: bool = False
    """Found on the pitched stems (no drums or vocals) rather than the whole mix."""


GRID_KEY_PATTERN = r"^[0-9a-f]{16}$"


class ChordDetectionState(ApiModel):
    """Where chord detection of a video on one beat grid stands, with the chords once done."""

    video_id: str
    grid: str | None = None
    """The beat grid (see chords.beat_grid_key); None: the song has no beat grid yet."""
    status: AnalysisStatus
    analysis: ChordAnalysis | None = None
    error: str | None = None


class MixerSettings(ApiModel):
    """The stem mixer of a video, part of its player.json."""

    enabled: bool = False
    """Play the stems instead of the video's own sound."""
    volumes: dict[StemName, Annotated[float, Field(ge=0, le=1)]] = Field(default_factory=dict)
    """Per stem; a stem not listed plays at 1."""
    muted: list[StemName] = Field(default_factory=list)
    solo: list[StemName] = Field(default_factory=list)
    """When not empty, only these stems are heard."""


PlayerSettings.model_rebuild()
Preset.model_rebuild()


USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,30}$"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_PRESETS = 200


class User(ApiModel):
    """A user account as the API returns it."""

    id: int
    username: str


class RegisterRequest(ApiModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    """3-30 letters, digits, '.', '_' or '-'; unique regardless of case."""
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class LoginRequest(ApiModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class DeleteAccountRequest(ApiModel):
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class GuestImportEntry(ApiModel):
    """A song from a guest's library in the browser, moved into the account on login."""

    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    presets: list[Preset] | None = Field(default=None, max_length=MAX_PRESETS)
    settings: PlayerSettings | None = None


MAX_DESCRIPTION_LENGTH = 300
MAX_PRACTICE_REPORT_SECONDS = 600
"""The player reports practice time at least this often."""

FollowState = Literal["none", "requested", "following", "self"]
"""How the viewer relates to a profile: 'requested' waits for a private profile's owner."""


class MyLibraryVideo(LibraryVideo):
    """A song in the logged-in user's library."""

    starred: bool = False


class MyLibraryEntry(ApiModel):
    video_id: str
    added_at: datetime
    starred: bool


class StarRequest(ApiModel):
    starred: bool


class UserSummary(ApiModel):
    """A user in a list (followers, requests)."""

    username: str
    description: str = ""


class Profile(ApiModel):
    """A user's profile as the viewer may see it."""

    username: str
    description: str
    is_private: bool
    joined_at: datetime
    followers: int
    following: int
    follow_state: FollowState
    can_view: bool
    """The viewer may see the songs and history: the profile is public, the viewer's own,
    or the viewer is an accepted follower."""
    library_count: int | None = None
    """None when the viewer may not see it (also below)."""
    practice_seconds: int | None = None
    """Practice time in all."""


class ProfileSettings(ApiModel):
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    is_private: bool = False


class PracticeEntry(ApiModel):
    """How long a user practiced a song on one day (UTC)."""

    video_id: str
    title: str
    day: date
    last_at: datetime
    """When the song was last played that day."""
    seconds: int


class FeedEntry(PracticeEntry):
    username: str


class PracticeReport(ApiModel):
    """The player's report: the music played this many more seconds."""

    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    seconds: int = Field(ge=1, le=MAX_PRACTICE_REPORT_SECONDS)


class ProfileLibrary(ApiModel):
    """The first songs of a user's library, most recently added first."""

    videos: list[LibraryVideo]
    total: int


NotificationKind = Literal["follow_request", "new_follower", "request_accepted"]
"""Someone asks to follow the user / started following them / accepted the user's request."""


class Notification(ApiModel):
    kind: NotificationKind
    username: str
    """The other user."""
    at: datetime
    unread: bool
    """Newer than when the user last opened the notifications."""
    follow_state: FollowState
    """How the user relates to the other user (e.g. whether they follow back)."""


class Notifications(ApiModel):
    items: list[Notification]
    unread: int
