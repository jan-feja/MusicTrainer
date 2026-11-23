"""Comments under songs. Under the song they show to everyone, a private profile's too;
the feed shows them like the rest of the user's activity (see practice_history.py)."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select

from music_trainer.db import CommentRow, Database, UserRow
from music_trainer.models import Comment
from music_trainer.services.accounts import utc_now


class Comments:
    def __init__(self, db: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def list(self, video_id: str, limit: int, before: datetime | None = None) -> list[Comment]:
        """The song's comments, newest first; `before` continues an earlier page."""
        query = (
            select(CommentRow, UserRow.username)
            .join(UserRow, UserRow.id == CommentRow.user_id)
            .where(CommentRow.video_id == video_id)
        )
        if before is not None:
            query = query.where(CommentRow.created_at < before)
        query = query.order_by(CommentRow.created_at.desc(), CommentRow.id.desc()).limit(limit)
        with self._db.session() as session:
            return [_comment(row, username) for row, username in session.execute(query)]

    def add(self, user_id: int, username: str, video_id: str, title: str, text: str) -> Comment:
        row = CommentRow(
            user_id=user_id, video_id=video_id, title=title, text=text, created_at=self._clock()
        )
        with self._db.session() as session, session.begin():
            session.add(row)
        return _comment(row, username)

    def delete(self, user_id: int, video_id: str, comment_id: int) -> bool:
        """Delete the user's own comment; returns False if there is no such comment of theirs."""
        with self._db.session() as session, session.begin():
            row = session.get(CommentRow, comment_id)
            if row is None or row.user_id != user_id or row.video_id != video_id:
                return False
            session.delete(row)
            return True


def _comment(row: CommentRow, username: str) -> Comment:
    return Comment(id=row.id, username=username, text=row.text, created_at=row.created_at)
