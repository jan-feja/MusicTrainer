"""/api/downloads: start downloads and follow their progress."""

from fastapi import APIRouter, HTTPException, status

from music_trainer.api.dependencies import DownloadsDependency, VideoIdParameter
from music_trainer.models import DownloadJob, DownloadRequest

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.post("", response_model=DownloadJob, status_code=status.HTTP_202_ACCEPTED)
def start_download(request: DownloadRequest, downloads: DownloadsDependency) -> DownloadJob:
    """Start a download; returns the existing job if the video is already (being) downloaded."""
    return downloads.start(request.video_id, request.title)


@router.get("", response_model=list[DownloadJob])
def list_downloads(downloads: DownloadsDependency) -> list[DownloadJob]:
    """Downloads started since the server was launched."""
    return downloads.list_jobs()


@router.get("/{video_id}", response_model=DownloadJob)
def get_download(video_id: VideoIdParameter, downloads: DownloadsDependency) -> DownloadJob:
    job = downloads.get(video_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No download for {video_id}")
    return job
