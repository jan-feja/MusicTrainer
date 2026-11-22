"""/api/library: downloaded videos, their media, thumbnails, saved loops and player settings."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from music_trainer.api.dependencies import (
    BeatAnalysisDependency,
    ChordDetectionDependency,
    DownloadsDependency,
    LibraryDependency,
    SettingsDependency,
    StemSeparationDependency,
    VideoIdParameter,
)
from music_trainer.models import LibraryVideo, PlayerSettings, SavedLoop, VideoMetadata
from music_trainer.services.audio import AudioDecodeError, extract_wav, ffmpeg_executable
from music_trainer.services.library import LibraryError, VideoNotInLibraryError

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
    video_id: VideoIdParameter,
    library: LibraryDependency,
    downloads: DownloadsDependency,
    beat_analysis: BeatAnalysisDependency,
    stem_separation: StemSeparationDependency,
    chord_detection: ChordDetectionDependency,
) -> Response:
    stem_separation.forget(video_id)  # stops a separation writing into the folder
    try:
        deleted = library.delete_video(video_id)
    except LibraryError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    if not deleted:
        raise _not_found(video_id)
    # so the video can be downloaded and analysed again
    downloads.forget(video_id)
    beat_analysis.forget(video_id)
    chord_detection.forget(video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


MAX_LOOPS = 200


@router.get("/{video_id}/loops", response_model=list[SavedLoop])
def get_loops(video_id: VideoIdParameter, library: LibraryDependency) -> list[SavedLoop]:
    """The loops saved with the video (stored in its loops.json)."""
    if not library.contains(video_id):
        raise _not_found(video_id)
    return library.read_loops(video_id)


@router.put("/{video_id}/loops", response_model=list[SavedLoop])
def put_loops(
    video_id: VideoIdParameter,
    library: LibraryDependency,
    loops: Annotated[list[SavedLoop], Body(max_length=MAX_LOOPS)],
) -> list[SavedLoop]:
    """Replace the saved loops."""
    if len({loop.id for loop in loops}) != len(loops):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Loop ids must be unique")
    try:
        library.write_loops(video_id, loops)
    except VideoNotInLibraryError as error:
        raise _not_found(video_id) from error
    return loops


@router.get("/{video_id}/settings", response_model=PlayerSettings)
def get_player_settings(video_id: VideoIdParameter, library: LibraryDependency) -> PlayerSettings:
    """How the player was left for the video (defaults if it was never opened)."""
    if not library.contains(video_id):
        raise _not_found(video_id)
    return library.read_player_settings(video_id) or PlayerSettings()


@router.put("/{video_id}/settings", response_model=PlayerSettings)
def put_player_settings(
    video_id: VideoIdParameter, library: LibraryDependency, settings: PlayerSettings
) -> PlayerSettings:
    try:
        library.write_player_settings(video_id, settings)
    except VideoNotInLibraryError as error:
        raise _not_found(video_id) from error
    return settings


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: VideoIdParameter, library: LibraryDependency) -> FileResponse:
    path = library.thumbnail_path(video_id)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No thumbnail for {video_id}")
    return FileResponse(path)
