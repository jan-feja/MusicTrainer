"""Gives route handlers access to the services created at startup."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi import Path as PathParameter

from music_trainer.config import Settings
from music_trainer.models import USERNAME_PATTERN, User
from music_trainer.services.accounts import Accounts
from music_trainer.services.beat_analysis import BeatAnalysisManager
from music_trainer.services.chord_detection import ChordDetectionManager
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library
from music_trainer.services.practice_history import PracticeHistory
from music_trainer.services.profiles import Profiles
from music_trainer.services.song_cleanup import SongCleanup
from music_trainer.services.stem_separation import StemSeparationManager
from music_trainer.services.user_library import UserLibrary
from music_trainer.services.youtube import YouTubeClient
from music_trainer.video_ids import VIDEO_ID_PATTERN


@dataclass(frozen=True)
class Services:
    settings: Settings
    library: Library
    youtube: YouTubeClient
    downloads: DownloadManager
    beat_analysis: BeatAnalysisManager
    stem_separation: StemSeparationManager
    chord_detection: ChordDetectionManager
    accounts: Accounts
    user_library: UserLibrary
    song_cleanup: SongCleanup
    profiles: Profiles
    practice_history: PracticeHistory


SESSION_COOKIE = "music_trainer_session"


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_settings(request: Request) -> Settings:
    return get_services(request).settings


def get_library(request: Request) -> Library:
    return get_services(request).library


def get_youtube(request: Request) -> YouTubeClient:
    return get_services(request).youtube


def get_downloads(request: Request) -> DownloadManager:
    return get_services(request).downloads


def get_beat_analysis(request: Request) -> BeatAnalysisManager:
    return get_services(request).beat_analysis


def get_stem_separation(request: Request) -> StemSeparationManager:
    return get_services(request).stem_separation


def get_chord_detection(request: Request) -> ChordDetectionManager:
    return get_services(request).chord_detection


def get_accounts(request: Request) -> Accounts:
    return get_services(request).accounts


def get_user_library(request: Request) -> UserLibrary:
    return get_services(request).user_library


def get_song_cleanup(request: Request) -> SongCleanup:
    return get_services(request).song_cleanup


def get_profiles(request: Request) -> Profiles:
    return get_services(request).profiles


def get_practice_history(request: Request) -> PracticeHistory:
    return get_services(request).practice_history


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def get_optional_user(request: Request) -> User | None:
    """The logged-in user, or None for a guest."""
    token = session_token(request)
    return get_accounts(request).user_for_token(token) if token else None


def get_required_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in first")
    return user


def require_account_to_change(user: User | None, what: str) -> None:
    """Analysis results are shared by everyone who has the song: guests cannot change them."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Log in to {what}")


SettingsDependency = Annotated[Settings, Depends(get_settings)]
LibraryDependency = Annotated[Library, Depends(get_library)]
YouTubeDependency = Annotated[YouTubeClient, Depends(get_youtube)]
DownloadsDependency = Annotated[DownloadManager, Depends(get_downloads)]
BeatAnalysisDependency = Annotated[BeatAnalysisManager, Depends(get_beat_analysis)]
StemSeparationDependency = Annotated[StemSeparationManager, Depends(get_stem_separation)]
ChordDetectionDependency = Annotated[ChordDetectionManager, Depends(get_chord_detection)]
AccountsDependency = Annotated[Accounts, Depends(get_accounts)]
UserLibraryDependency = Annotated[UserLibrary, Depends(get_user_library)]
SongCleanupDependency = Annotated[SongCleanup, Depends(get_song_cleanup)]
ProfilesDependency = Annotated[Profiles, Depends(get_profiles)]
PracticeHistoryDependency = Annotated[PracticeHistory, Depends(get_practice_history)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
RequiredUser = Annotated[User, Depends(get_required_user)]
VideoIdParameter = Annotated[
    str, PathParameter(pattern=VIDEO_ID_PATTERN, description="YouTube video ID")
]
UsernameParameter = Annotated[str, PathParameter(pattern=USERNAME_PATTERN)]
