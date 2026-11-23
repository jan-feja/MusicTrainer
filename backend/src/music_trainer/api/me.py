"""/api/me/library: the logged-in user's library, with their presets and player settings.

Guests keep their library in the browser; these routes need an account.
"""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from music_trainer.api.dependencies import (
    DownloadsDependency,
    LibraryDependency,
    PracticeHistoryDependency,
    RequiredUser,
    SongCleanupDependency,
    UserLibraryDependency,
    VideoIdParameter,
)
from music_trainer.api.library import to_library_video
from music_trainer.models import (
    MAX_PRESETS,
    FollowedPresets,
    GuestImportEntry,
    MyLibraryEntry,
    MyLibraryVideo,
    PlayerSettings,
    Preset,
    StarRequest,
)
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library

router = APIRouter(prefix="/api/me/library", tags=["my library"])

MAX_IMPORTED_SONGS = 1000
MAX_RANDOM_SONGS = 24


def _not_in_library(video_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Video {video_id} is not in your library")


def _song_available(video_id: str, library: Library, downloads: DownloadManager) -> bool:
    """On the server, or being downloaded."""
    if library.contains(video_id):
        return True
    job = downloads.get(video_id)
    return job is not None and job.status.is_active


@router.get("", response_model=list[MyLibraryVideo])
def list_my_videos(
    user: RequiredUser, user_library: UserLibraryDependency, library: LibraryDependency
) -> list[MyLibraryVideo]:
    """The songs in the library, most recently added first (not those still downloading)."""
    starred = set(user_library.starred_ids(user.id))
    videos = (library.get_video(video_id) for video_id in user_library.video_ids(user.id))
    return [
        MyLibraryVideo(**to_library_video(video).model_dump(), starred=video.video_id in starred)
        for video in videos
        if video is not None
    ]


@router.get("/random", response_model=list[MyLibraryVideo])
def random_my_videos(
    user: RequiredUser,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    count: Annotated[int, Query(ge=1, le=MAX_RANDOM_SONGS)] = 6,
) -> list[MyLibraryVideo]:
    """A few songs of the library, picked at random (for the home page)."""
    starred = set(user_library.starred_ids(user.id))
    videos = (library.get_video(video_id) for video_id in user_library.random_ids(user.id, count))
    return [
        MyLibraryVideo(**to_library_video(video).model_dump(), starred=video.video_id in starred)
        for video in videos
        if video is not None
    ]


@router.get("/{video_id}", response_model=MyLibraryEntry)
def get_entry(
    video_id: VideoIdParameter, user: RequiredUser, user_library: UserLibraryDependency
) -> MyLibraryEntry:
    """The song's place in the library: when it was added, starred or not."""
    entry = user_library.entry(user.id, video_id)
    if entry is None:
        raise _not_in_library(video_id)
    return entry


@router.put("/{video_id}/star", status_code=status.HTTP_204_NO_CONTENT)
def star_video(
    video_id: VideoIdParameter,
    body: StarRequest,
    user: RequiredUser,
    user_library: UserLibraryDependency,
) -> Response:
    """Star or unstar a song of the library (starred songs show on the profile)."""
    if not user_library.set_starred(user.id, video_id, body.starred):
        raise _not_in_library(video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_video(
    video_id: VideoIdParameter,
    user: RequiredUser,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    downloads: DownloadsDependency,
) -> Response:
    """Add a song that is on the server (or being downloaded) to the library."""
    if not _song_available(video_id, library, downloads):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Video {video_id} is not on the server")
    user_library.add(user.id, video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_video(
    video_id: VideoIdParameter,
    user: RequiredUser,
    user_library: UserLibraryDependency,
    song_cleanup: SongCleanupDependency,
) -> Response:
    """Remove the song from the library, with the presets; deletes it if nobody else has it."""
    if not user_library.remove(user.id, video_id):
        raise _not_in_library(video_id)
    song_cleanup.release(video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{video_id}/presets", response_model=list[Preset])
def get_presets(
    video_id: VideoIdParameter, user: RequiredUser, user_library: UserLibraryDependency
) -> list[Preset]:
    presets = user_library.read_presets(user.id, video_id)
    if presets is None:
        raise _not_in_library(video_id)
    return presets


@router.put("/{video_id}/presets", response_model=list[Preset])
def put_presets(
    video_id: VideoIdParameter,
    user: RequiredUser,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    history: PracticeHistoryDependency,
    presets: Annotated[list[Preset], Body(max_length=MAX_PRESETS)],
) -> list[Preset]:
    """Replace the presets; new ones show in the user's history (and the feed)."""
    if len({preset.id for preset in presets}) != len(presets):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Preset ids must be unique")
    before = user_library.read_presets(user.id, video_id)
    if before is None or not user_library.write_presets(user.id, video_id, presets):
        raise _not_in_library(video_id)
    video = library.get_video(video_id)
    if video is not None:
        history.presets_changed(user.id, video_id, video.title, before, presets)
    return presets


@router.get("/{video_id}/followed-presets", response_model=list[FollowedPresets])
def get_followed_presets(
    video_id: VideoIdParameter, user: RequiredUser, user_library: UserLibraryDependency
) -> list[FollowedPresets]:
    """The presets of the song made by the users the user follows (to copy, not to change)."""
    return user_library.followed_presets(user.id, video_id)


@router.get("/{video_id}/settings", response_model=PlayerSettings)
def get_player_settings(
    video_id: VideoIdParameter, user: RequiredUser, user_library: UserLibraryDependency
) -> PlayerSettings:
    """How the player was left for the song (defaults if it was never opened)."""
    settings = user_library.read_settings(user.id, video_id)
    if settings is None:
        raise _not_in_library(video_id)
    return settings


@router.put("/{video_id}/settings", response_model=PlayerSettings)
def put_player_settings(
    video_id: VideoIdParameter,
    user: RequiredUser,
    user_library: UserLibraryDependency,
    settings: PlayerSettings,
) -> PlayerSettings:
    if not user_library.write_settings(user.id, video_id, settings):
        raise _not_in_library(video_id)
    return settings


@router.post("/import", status_code=status.HTTP_204_NO_CONTENT)
def import_guest_library(
    user: RequiredUser,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    downloads: DownloadsDependency,
    entries: Annotated[list[GuestImportEntry], Body(max_length=MAX_IMPORTED_SONGS)],
) -> Response:
    """Move a guest's library from the browser into the account after logging in.

    Songs no longer on the server are skipped; presets and settings are kept only for
    songs the account has none for yet.
    """
    available = [e for e in entries if _song_available(e.video_id, library, downloads)]
    user_library.import_guest(user.id, available)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
