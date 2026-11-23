"""/api/library/{video_id}/chords: the chords of a downloaded video, on a beat grid.

Chords are kept per grid: the detected one, or a user's own (with their fixes).
"""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, status

from music_trainer.api.dependencies import (
    BeatAnalysisDependency,
    ChordDetectionDependency,
    OptionalUser,
    VideoIdParameter,
    require_account_to_change,
)
from music_trainer.models import (
    GRID_KEY_PATTERN,
    AnalysisStatus,
    BeatGridHints,
    ChordDetectionState,
)
from music_trainer.services.beat_analysis import BeatsNotDetectedError
from music_trainer.services.beats import NO_HINTS
from music_trainer.services.chords import beat_grid_key
from music_trainer.services.library import VideoNotInLibraryError

router = APIRouter(prefix="/api/library", tags=["chords"])


@router.get("/{video_id}/chords", response_model=ChordDetectionState)
def get_chords(
    video_id: VideoIdParameter,
    detection: ChordDetectionDependency,
    beats: BeatAnalysisDependency,
    grid: Annotated[
        str | None,
        Query(
            pattern=GRID_KEY_PATTERN,
            description="The beat grid, as `grid` in the state POST returned; default: detected",
        ),
    ] = None,
) -> ChordDetectionState:
    """State of chord detection on a grid; contains the chords once it is `completed`."""
    try:
        if grid is None:
            detected = beats.detected(video_id)
            if detected is None:
                return ChordDetectionState(video_id=video_id, status=AnalysisStatus.NOT_STARTED)
            grid = beat_grid_key(detected)
        return detection.get_state(video_id, grid)
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
    beats: BeatAnalysisDependency,
    user: OptionalUser,
    hints: Annotated[
        BeatGridHints | None, Body(description="The user's beat grid fixes; default: none")
    ] = None,
    force: Annotated[bool, Query(description="Detect again even if chords exist")] = False,
) -> ChordDetectionState:
    """Start chord detection on the user's beat grid (a few seconds, in the background).

    Poll GET with the returned `grid`. 409 while the beats are not detected yet.
    `force` needs an account (the chords are shared by everyone with the same grid).
    """
    if force:
        require_account_to_change(user, "detect the chords again")
    try:
        grid = beats.grid(video_id, hints or NO_HINTS)
        return detection.start(video_id, grid, force=force)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except BeatsNotDetectedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{error}; chords need them") from error
