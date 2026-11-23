"""/api/users/{username}: profiles, their songs and history, and following them.

A private profile's songs, history and follower lists are shown only to its
owner and accepted followers (403 for others); the profile itself (username,
description, counts) is open to everyone.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from music_trainer.api.dependencies import (
    LibraryDependency,
    OptionalUser,
    PracticeHistoryDependency,
    ProfilesDependency,
    RequiredUser,
    UserLibraryDependency,
    UsernameParameter,
)
from music_trainer.api.library import to_library_video
from music_trainer.models import (
    FollowState,
    LibraryVideo,
    PracticeEntry,
    Profile,
    ProfileLibrary,
    User,
    UserSummary,
)
from music_trainer.services.library import Library
from music_trainer.services.profiles import ProfileOwner, Profiles

router = APIRouter(prefix="/api/users", tags=["users"])

MAX_PAGE = 100


def _find(username: str, profiles: Profiles) -> ProfileOwner:
    owner = profiles.find(username)
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"There is no user {username}")
    return owner


def _viewable(username: str, viewer: User | None, profiles: Profiles) -> ProfileOwner:
    """The owner, if the viewer may see their songs and history; 403 for a private profile."""
    owner = _find(username, profiles)
    if not profiles.can_view(viewer.id if viewer else None, owner):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{owner.username}'s profile is private")
    return owner


def _videos(video_ids: list[str], library: Library) -> list[LibraryVideo]:
    """The songs still on the server, in the given order."""
    videos = (library.get_video(video_id) for video_id in video_ids)
    return [to_library_video(video) for video in videos if video is not None]


@router.get("/{username}", response_model=Profile)
def get_profile(
    username: UsernameParameter,
    viewer: OptionalUser,
    profiles: ProfilesDependency,
    user_library: UserLibraryDependency,
    history: PracticeHistoryDependency,
) -> Profile:
    owner = _find(username, profiles)
    viewer_id = viewer.id if viewer else None
    state = profiles.follow_state(viewer_id, owner)
    can_view = profiles.can_view(viewer_id, owner)
    followers, following = profiles.counts(owner.id)
    return Profile(
        username=owner.username,
        description=owner.description,
        is_private=owner.is_private,
        joined_at=owner.joined_at,
        followers=followers,
        following=following,
        follow_state=state,
        can_view=can_view,
        library_count=user_library.count(owner.id) if can_view else None,
        practice_seconds=history.total_seconds(owner.id) if can_view else None,
    )


@router.get("/{username}/starred", response_model=list[LibraryVideo])
def get_starred(
    username: UsernameParameter,
    viewer: OptionalUser,
    profiles: ProfilesDependency,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
) -> list[LibraryVideo]:
    """The user's starred songs, most recently starred first."""
    owner = _viewable(username, viewer, profiles)
    return _videos(user_library.starred_ids(owner.id), library)


@router.get("/{username}/library", response_model=ProfileLibrary)
def get_library(
    username: UsernameParameter,
    viewer: OptionalUser,
    profiles: ProfilesDependency,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    limit: Annotated[int, Query(ge=1, le=1000)] = 12,
) -> ProfileLibrary:
    """The user's most recently added songs, and how many there are in all."""
    owner = _viewable(username, viewer, profiles)
    return ProfileLibrary(
        videos=_videos(user_library.video_ids(owner.id, limit), library),
        total=user_library.count(owner.id),
    )


@router.get("/{username}/history", response_model=list[PracticeEntry])
def get_history(
    username: UsernameParameter,
    viewer: OptionalUser,
    profiles: ProfilesDependency,
    history: PracticeHistoryDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 30,
    before: Annotated[
        datetime | None, Query(description="`lastAt` of the last entry of the previous page")
    ] = None,
) -> list[PracticeEntry]:
    """What the user practiced: one entry per song and day, newest first."""
    owner = _viewable(username, viewer, profiles)
    return history.history(owner.id, limit, before)


@router.get("/{username}/followers", response_model=list[UserSummary])
def get_followers(
    username: UsernameParameter, viewer: OptionalUser, profiles: ProfilesDependency
) -> list[UserSummary]:
    return profiles.followers(_viewable(username, viewer, profiles).id)


@router.get("/{username}/following", response_model=list[UserSummary])
def get_following(
    username: UsernameParameter, viewer: OptionalUser, profiles: ProfilesDependency
) -> list[UserSummary]:
    return profiles.following(_viewable(username, viewer, profiles).id)


@router.put("/{username}/follow", response_model=FollowState)
def follow(username: UsernameParameter, user: RequiredUser, profiles: ProfilesDependency) -> str:
    """Follow the user; a private profile gets a request ('requested') instead."""
    owner = _find(username, profiles)
    if owner.id == user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You cannot follow yourself")
    return profiles.follow(user.id, owner)


@router.delete("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(
    username: UsernameParameter, user: RequiredUser, profiles: ProfilesDependency
) -> Response:
    """Stop following the user, or take back the request."""
    profiles.unfollow(user.id, _find(username, profiles).id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
