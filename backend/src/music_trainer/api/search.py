"""GET /api/search: search YouTube."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import (
    LibraryDependency,
    OptionalUser,
    UserLibraryDependency,
    YouTubeDependency,
)
from music_trainer.models import SearchResult
from music_trainer.services.youtube import YouTubeError

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(
    youtube: YouTubeDependency,
    library: LibraryDependency,
    user: OptionalUser,
    user_library: UserLibraryDependency,
    q: Annotated[str, Query(min_length=1, max_length=300, description="Search text or video link")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchResult]:
    try:
        results = youtube.search(q.strip(), limit)
    except YouTubeError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"YouTube search failed: {error}"
        ) from error
    mine = set(user_library.video_ids(user.id)) if user is not None else set()
    return [
        result.model_copy(
            update={
                "is_downloaded": library.contains(result.video_id),
                "in_library": result.video_id in mine,
            }
        )
        for result in results
    ]
