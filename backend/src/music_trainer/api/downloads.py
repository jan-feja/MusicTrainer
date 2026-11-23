"""/api/downloads: start downloads and follow their progress."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import (
    DownloadsDependency,
    OptionalUser,
    UserLibraryDependency,
    VideoIdParameter,
)
from music_trainer.models import DownloadJob, DownloadRequest

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.post("", response_model=DownloadJob, status_code=status.HTTP_202_ACCEPTED)
def start_download(
    request: DownloadRequest,
    downloads: DownloadsDependency,
    user: OptionalUser,
    user_library: UserLibraryDependency,
) -> DownloadJob:
    """Start a download; returns the existing job if the video is already (being) downloaded.

    The song goes into the user's library at once; a guest keeps it in the browser.
    """
    if user is not None:
        user_library.add(user.id, request.video_id)
    else:
        user_library.touch_guest_use(request.video_id)
    return downloads.start(request.video_id, request.title)


@router.get("", response_model=list[DownloadJob])
def list_downloads(
    downloads: DownloadsDependency,
    user: OptionalUser,
    user_library: UserLibraryDependency,
    ids: Annotated[
        list[str], Query(description="For a guest: the videos in the browser's library")
    ] = [],  # noqa: B006 (FastAPI copies the default)
) -> list[DownloadJob]:
    """Downloads started since the server was launched, of the songs in the user's library."""
    wanted = set(user_library.video_ids(user.id)) if user is not None else set(ids)
    return [job for job in downloads.list_jobs() if job.video_id in wanted]


@router.get("/{video_id}", response_model=DownloadJob)
def get_download(video_id: VideoIdParameter, downloads: DownloadsDependency) -> DownloadJob:
    job = downloads.get(video_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No download for {video_id}")
    return job
