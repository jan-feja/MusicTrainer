"""/api/library/{video_id}/beats: beat and bar detection of a downloaded video."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, status

from music_trainer.api.dependencies import (
    BeatAnalysisDependency,
    OptionalUser,
    VideoIdParameter,
    require_account_to_change,
)
from music_trainer.models import BeatGridHints, BeatTrackingState
from music_trainer.services.library import VideoNotInLibraryError

router = APIRouter(prefix="/api/library", tags=["beats"])


@router.get("/{video_id}/beats", response_model=BeatTrackingState)
def get_beats(video_id: VideoIdParameter, analysis: BeatAnalysisDependency) -> BeatTrackingState:
    """State of beat detection; contains the beat grid once it is `completed`."""
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
    hints: Annotated[
        BeatGridHints | None,
        Body(
            description="Decode the grid again with these hints (fast: the network output is kept)"
        ),
    ] = None,
) -> BeatTrackingState:
    """Start beat detection (runs in the background; poll GET for the result).

    The grid is shared by everyone who has the song: `force` and `hints` need an account.
    """
    if force or hints is not None:
        require_account_to_change(user, "fix the beat grid")
    try:
        return analysis.start(video_id, force=force, hints=hints)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
