"""/api/library: the songs on the server, their media and thumbnails.

There is no list of all songs: each user has their own library (/api/me/library,
or the browser for guests). A song is found by its YouTube video ID.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from music_trainer.api.dependencies import (
    LibraryDependency,
    OptionalUser,
    SettingsDependency,
    UserLibraryDependency,
    VideoIdParameter,
)
from music_trainer.models import LibraryVideo, VideoMetadata
from music_trainer.services.audio import AudioDecodeError, extract_wav, ffmpeg_executable

router = APIRouter(prefix="/api/library", tags=["library"])


def to_library_video(metadata: VideoMetadata) -> LibraryVideo:
    base_url = f"{router.prefix}/{metadata.video_id}"
    return LibraryVideo(
        **metadata.model_dump(exclude={"media_file", "thumbnail_file"}),
        media_url=f"{base_url}/media",
        audio_url=f"{base_url}/audio",
        thumbnail_url=f"{base_url}/thumbnail" if metadata.thumbnail_file else None,
    )


def _not_found(video_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Video {video_id} is not in the library")


@router.get("/{video_id}", response_model=LibraryVideo)
def get_video(
    video_id: VideoIdParameter,
    library: LibraryDependency,
    user: OptionalUser,
    user_library: UserLibraryDependency,
) -> LibraryVideo:
    """A song on the server, whoever has it (guests open songs by their ID)."""
    metadata = library.get_video(video_id)
    if metadata is None:
        raise _not_found(video_id)
    if user is None:
        user_library.touch_guest_use(video_id)  # keeps the song from being cleaned up
    return to_library_video(metadata)


@router.get("/{video_id}/media")
def get_media(video_id: VideoIdParameter, library: LibraryDependency) -> FileResponse:
    """The video file. Supports HTTP range requests, which the player needs for seeking."""
    path = library.media_path(video_id)
    if path is None:
        raise _not_found(video_id)
    return FileResponse(path)


# a loop longer than this keeps the plain seek back to its start
MAX_AUDIO_SECONDS = 900


@router.get("/{video_id}/audio", response_class=Response)
def get_audio(
    video_id: VideoIdParameter,
    library: LibraryDependency,
    settings: SettingsDependency,
    start: Annotated[float, Query(ge=0, description="First second")],
    end: Annotated[float, Query(gt=0, description="Last second")],
    sample_rate: Annotated[int, Query(alias="sampleRate", ge=8000, le=192000)] = 48000,
) -> Response:
    """
    A section of the audio as a 16-bit stereo WAV file. The player loops it in
    the browser, so the jump back to the loop start has no gap.
    """
    if not 0 < end - start <= MAX_AUDIO_SECONDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"end must be after start, by at most {MAX_AUDIO_SECONDS} s",
        )
    path = library.media_path(video_id)
    if path is None:
        raise _not_found(video_id)
    try:
        wav = extract_wav(path, start, end, sample_rate, ffmpeg_executable(settings.ffmpeg_path))
    except AudioDecodeError as error:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(error)) from error
    return Response(wav, media_type="audio/wav")


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: VideoIdParameter, library: LibraryDependency) -> FileResponse:
    path = library.thumbnail_path(video_id)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No thumbnail for {video_id}")
    return FileResponse(path)
