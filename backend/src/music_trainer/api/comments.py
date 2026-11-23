"""/api/library/{video_id}/comments: what users wrote under a song.

Everyone can read them; writing needs an account, and only the author can delete
a comment. A private profile's comments show here too (but not in the everyone feed).
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from music_trainer.api.dependencies import (
    CommentsDependency,
    LibraryDependency,
    RequiredUser,
    VideoIdParameter,
)
from music_trainer.models import Comment, NewComment

router = APIRouter(prefix="/api/library", tags=["comments"])


@router.get("/{video_id}/comments", response_model=list[Comment])
def list_comments(
    video_id: VideoIdParameter,
    comments: CommentsDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[
        datetime | None, Query(description="`createdAt` of the last comment of the previous page")
    ] = None,
) -> list[Comment]:
    """Newest first."""
    return comments.list(video_id, limit, before)


@router.post("/{video_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
def add_comment(
    video_id: VideoIdParameter,
    body: NewComment,
    user: RequiredUser,
    comments: CommentsDependency,
    library: LibraryDependency,
) -> Comment:
    text = body.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The comment is empty")
    video = library.get_video(video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Song not found")
    return comments.add(user.id, user.username, video_id, video.title, text)


@router.delete("/{video_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    video_id: VideoIdParameter, comment_id: int, user: RequiredUser, comments: CommentsDependency
) -> Response:
    if not comments.delete(user.id, video_id, comment_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such comment of yours")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
