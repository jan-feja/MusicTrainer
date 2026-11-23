"""/api/me: the logged-in user's profile settings, notifications, followers and practice."""

from fastapi import APIRouter, HTTPException, Response, status

from music_trainer.api.dependencies import (
    LibraryDependency,
    PracticeHistoryDependency,
    ProfilesDependency,
    RequiredUser,
    UserLibraryDependency,
    UsernameParameter,
)
from music_trainer.models import Notifications, PracticeReport, ProfileSettings
from music_trainer.services.profiles import ProfileOwner, Profiles

router = APIRouter(prefix="/api/me", tags=["my profile"])


def _find(username: str, profiles: Profiles) -> ProfileOwner:
    owner = profiles.find(username)
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"There is no user {username}")
    return owner


@router.get("/profile", response_model=ProfileSettings)
def get_profile_settings(user: RequiredUser, profiles: ProfilesDependency) -> ProfileSettings:
    return profiles.settings(user.id)


@router.put("/profile", response_model=ProfileSettings)
def put_profile_settings(
    body: ProfileSettings, user: RequiredUser, profiles: ProfilesDependency
) -> ProfileSettings:
    """Change the description and privacy; going public accepts the waiting requests."""
    profiles.update_settings(user.id, body)
    return profiles.settings(user.id)


@router.get("/notifications", response_model=Notifications)
def get_notifications(user: RequiredUser, profiles: ProfilesDependency) -> Notifications:
    """Follow requests waiting for an answer, new followers, accepted requests; and how many
    are unread."""
    return profiles.notifications(user.id)


@router.post("/notifications/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_seen(user: RequiredUser, profiles: ProfilesDependency) -> Response:
    """The user opened the notifications: what is there now is no longer unread."""
    profiles.mark_notifications_seen(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/followers/{username}", status_code=status.HTTP_204_NO_CONTENT)
def accept_follower(
    username: UsernameParameter, user: RequiredUser, profiles: ProfilesDependency
) -> Response:
    """Accept a follow request."""
    if not profiles.accept(user.id, _find(username, profiles).id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{username} did not ask to follow you")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/followers/{username}", status_code=status.HTTP_204_NO_CONTENT)
def remove_follower(
    username: UsernameParameter, user: RequiredUser, profiles: ProfilesDependency
) -> Response:
    """Decline a follow request, or remove a follower."""
    profiles.unfollow(_find(username, profiles).id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/practice", status_code=status.HTTP_204_NO_CONTENT)
def report_practice(
    body: PracticeReport,
    user: RequiredUser,
    user_library: UserLibraryDependency,
    library: LibraryDependency,
    history: PracticeHistoryDependency,
) -> Response:
    """The player played a song of the library for `seconds` more (adds to today's entry)."""
    video = library.get_video(body.video_id)
    if video is None or user_library.entry(user.id, body.video_id) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Video {body.video_id} is not in your library"
        )
    history.record(user.id, body.video_id, video.title, body.seconds)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
