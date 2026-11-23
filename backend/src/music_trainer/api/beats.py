"""/api/library/{video_id}/beats: beat and bar detection of a downloaded video.

The detected grid is shared by everyone who has the song; a user's fixes of it
(hints) give their own grid, which their browser keeps with their player settings.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import (
    BeatAnalysisDependency,
    OptionalUser,
    VideoIdParameter,
    require_account_to_change,
)
from music_trainer.models import BeatAnalysis, BeatGridHints, BeatTrackingState
from music_trainer.services.beat_analysis import BeatsNotDetectedError
from music_trainer.services.library import VideoNotInLibraryError

router = APIRouter(prefix="/api/library", tags=["beats"])


@router.get("/{video_id}/beats", response_model=BeatTrackingState)
def get_beats(video_id: VideoIdParameter, analysis: BeatAnalysisDependency) -> BeatTrackingState:
    """State of beat detection; contains the detected grid once it is `completed`."""
    try:
        return analysis.get_state(video_id)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.post(
    "/{video_id}/beats", response_model=BeatTrackingState, status_code=status.HTTP_202_ACCEPTED
)
def detect_beats(
    video_id: VideoIdParameter,
    analysis: BeatAnalysisDependency,
    user: OptionalUser,
    force: Annotated[bool, Query(description="Run the beat network again")] = False,
) -> BeatTrackingState:
    """Start beat detection (runs in the background; poll GET for the result).

    `force` needs an account: the detection is shared by everyone who has the song.
    """
    if force:
        require_account_to_change(user, "detect the beats again")
    try:
        return analysis.start(video_id, force=force)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.post("/{video_id}/beats/grid", response_model=BeatAnalysis)
def fixed_grid(
    video_id: VideoIdParameter, analysis: BeatAnalysisDependency, hints: BeatGridHints
) -> BeatAnalysis:
    """The beat grid with the user's fixes (a moment for a new tempo or meter).

    409 while the beats are not detected yet.
    """
    try:
        return analysis.grid(video_id, hints)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except BeatsNotDetectedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
