"""/api/library/{video_id}/chords: the chords of a downloaded video, on its beat grid."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import (
    ChordDetectionDependency,
    OptionalUser,
    VideoIdParameter,
    require_account_to_change,
)
from music_trainer.models import ChordDetectionState
from music_trainer.services.chord_detection import NoBeatGridError
from music_trainer.services.library import VideoNotInLibraryError

router = APIRouter(prefix="/api/library", tags=["chords"])


@router.get("/{video_id}/chords", response_model=ChordDetectionState)
def get_chords(
    video_id: VideoIdParameter, detection: ChordDetectionDependency
) -> ChordDetectionState:
    """State of chord detection; contains the chords once it is `completed`."""
    try:
        return detection.get_state(video_id)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.post(
    "/{video_id}/chords",
    response_model=ChordDetectionState,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_chords(
    video_id: VideoIdParameter,
    detection: ChordDetectionDependency,
    user: OptionalUser,
    force: Annotated[bool, Query(description="Detect again even if chords exist")] = False,
) -> ChordDetectionState:
    """Start chord detection (a few seconds, in the background; poll GET).

    Needs the beat grid: 409 while the beats are not detected yet. `force` needs an
    account (the chords are shared by everyone who has the song).
    """
    if force:
        require_account_to_change(user, "detect the chords again")
    try:
        return detection.start(video_id, force=force)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except NoBeatGridError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
