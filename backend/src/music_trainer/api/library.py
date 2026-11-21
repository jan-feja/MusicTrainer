"""/api/library: downloaded videos, their media files and thumbnails."""

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse

from music_trainer.api.dependencies import (
    DownloadsDependency,
    LibraryDependency,
    VideoIdParameter,
)
from music_trainer.models import LibraryVideo, VideoMetadata
from music_trainer.services.library import LibraryError

router = APIRouter(prefix="/api/library", tags=["library"])


def to_library_video(metadata: VideoMetadata) -> LibraryVideo:
    base_url = f"{router.prefix}/{metadata.video_id}"
    return LibraryVideo(
        **metadata.model_dump(exclude={"media_file", "thumbnail_file"}),
        media_url=f"{base_url}/media",
        thumbnail_url=f"{base_url}/thumbnail" if metadata.thumbnail_file else None,
    )


def _not_found(video_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Video {video_id} is not in the library")


@router.get("", response_model=list[LibraryVideo])
def list_videos(library: LibraryDependency) -> list[LibraryVideo]:
    return [to_library_video(video) for video in library.list_videos()]


@router.get("/{video_id}", response_model=LibraryVideo)
def get_video(video_id: VideoIdParameter, library: LibraryDependency) -> LibraryVideo:
    metadata = library.get_video(video_id)
    if metadata is None:
        raise _not_found(video_id)
    return to_library_video(metadata)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: VideoIdParameter, library: LibraryDependency, downloads: DownloadsDependency
) -> Response:
    try:
        deleted = library.delete_video(video_id)
    except LibraryError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    if not deleted:
        raise _not_found(video_id)
    downloads.forget(video_id)  # so the video can be downloaded again
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{video_id}/media")
def get_media(video_id: VideoIdParameter, library: LibraryDependency) -> FileResponse:
    """The video file. Supports HTTP range requests, which the player needs for seeking."""
    path = library.media_path(video_id)
    if path is None:
        raise _not_found(video_id)
    return FileResponse(path)


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: VideoIdParameter, library: LibraryDependency) -> FileResponse:
    path = library.thumbnail_path(video_id)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No thumbnail for {video_id}")
    return FileResponse(path)
