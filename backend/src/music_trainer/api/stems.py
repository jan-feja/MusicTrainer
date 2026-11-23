"""/api/library/{video_id}/stems: a downloaded video separated into instruments."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi import Path as PathParameter
from fastapi.responses import FileResponse

from music_trainer.api.dependencies import (
    LibraryDependency,
    StemSeparationDependency,
    VideoIdParameter,
)
from music_trainer.models import STEM_NAME_PATTERN, StemSeparationState
from music_trainer.services.library import VideoNotInLibraryError

router = APIRouter(prefix="/api/library", tags=["stems"])

StemNameParameter = Annotated[
    str, PathParameter(pattern=STEM_NAME_PATTERN, description="Stem name, e.g. 'drums'")
]


@router.get("/{video_id}/stems", response_model=StemSeparationState)
def get_stems(
    video_id: VideoIdParameter, separation: StemSeparationDependency
) -> StemSeparationState:
    """State of the separation; lists the stems once it is `completed`."""
    try:
        return separation.get_state(video_id)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.post(
    "/{video_id}/stems",
    response_model=StemSeparationState,
    status_code=status.HTTP_202_ACCEPTED,
)
def separate_stems(
    video_id: VideoIdParameter,
    separation: StemSeparationDependency,
    force: Annotated[bool, Query(description="Separate again even if stems exist")] = False,
) -> StemSeparationState:
    """Separate this song next (runs in the background, ~2 min per song on a CPU; poll GET).

    Called by the player for the open song: moves it to the front of the queue.
    """
    try:
        return separation.start(video_id, force=force, first=True)
    except VideoNotInLibraryError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.get("/{video_id}/stems/{name}", response_class=FileResponse)
def get_stem(
    video_id: VideoIdParameter, name: StemNameParameter, library: LibraryDependency
) -> FileResponse:
    """One stem as a FLAC file, the same length as the video's audio."""
    path = library.stem_path(video_id, name)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No stem {name} for video {video_id}")
    return FileResponse(path, media_type="audio/flac")
