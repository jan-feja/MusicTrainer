"""/api/feed: what people practiced lately, one entry per user, song and day."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from music_trainer.api.dependencies import OptionalUser, PracticeHistoryDependency
from music_trainer.models import FeedEntry
from music_trainer.services.practice_history import FeedScope

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("", response_model=list[FeedEntry])
def get_feed(
    viewer: OptionalUser,
    history: PracticeHistoryDependency,
    scope: Annotated[
        FeedScope,
        Query(description="'everyone': public profiles; 'following': the users you follow"),
    ] = "everyone",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[
        datetime | None, Query(description="`lastAt` of the last entry of the previous page")
    ] = None,
) -> list[FeedEntry]:
    if scope == "following" and viewer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in to see whom you follow")
    return history.feed(scope, viewer.id if viewer else None, limit, before)
