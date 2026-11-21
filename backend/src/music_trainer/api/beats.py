"""/api/library/{video_id}/beats: beat and bar detection of a downloaded video."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import BeatAnalysisDependency, VideoIdParameter
from music_trainer.models import BeatTrackingState
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
    force: Annotated[bool, Query(description="Detect again even if a result exists")] = False,
) -> BeatTrackingState:
    """Start beat detection (runs in the background; poll GET for the result)."""
    try:
        return analysis.start(video_id, force=force)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
