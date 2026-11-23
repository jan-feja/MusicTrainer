"""What users practiced: one entry per user, song and day, with the time the music played.

The player reports the playing time in small parts; they add up in the day's
entry, so opening a song ten times a day is still one entry. Entries under
MIN_SHOWN_SECONDS (a song opened and left) are kept but not shown.

The feed lists the newest entries of public profiles, or of the users one follows.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select

from music_trainer.db import Database, FollowRow, PracticeDayRow, UserRow
from music_trainer.models import FeedEntry, PracticeEntry
from music_trainer.services.accounts import utc_now

MIN_SHOWN_SECONDS = 30
FeedScope = Literal["everyone", "following"]


class PracticeHistory:
    def __init__(self, db: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def record(self, user_id: int, video_id: str, title: str, seconds: int) -> None:
        """The song played `seconds` more for the user (added to today's entry)."""
        now = self._clock()
        with self._db.session() as session, session.begin():
            row = session.get(PracticeDayRow, (user_id, video_id, now.date()))
            if row is None:
                session.add(
                    PracticeDayRow(
                        user_id=user_id,
                        video_id=video_id,
                        day=now.date(),
                        title=title,
                        last_at=now,
                        seconds=seconds,
                    )
                )
            else:
                row.seconds += seconds
                row.last_at = now
                row.title = title

    def history(
        self, user_id: int, limit: int, before: datetime | None = None
    ) -> list[PracticeEntry]:
        """The user's entries, newest first; `before` continues an earlier page."""
        query = select(PracticeDayRow).where(
            PracticeDayRow.user_id == user_id, PracticeDayRow.seconds >= MIN_SHOWN_SECONDS
        )
        if before is not None:
            query = query.where(PracticeDayRow.last_at < before)
        with self._db.session() as session:
            rows = session.scalars(query.order_by(PracticeDayRow.last_at.desc()).limit(limit))
            return [_entry(row) for row in rows]

    def total_seconds(self, user_id: int) -> int:
        with self._db.session() as session:
            total = session.scalar(
                select(func.sum(PracticeDayRow.seconds)).where(PracticeDayRow.user_id == user_id)
            )
            return int(total or 0)

    def feed(
        self,
        scope: FeedScope,
        viewer_id: int | None,
        limit: int,
        before: datetime | None = None,
    ) -> list[FeedEntry]:
        """The newest entries of public profiles ('everyone'), or of the users the viewer
        follows ('following', private ones too once they accepted)."""
        query = (
            select(PracticeDayRow, UserRow.username)
            .join(UserRow, UserRow.id == PracticeDayRow.user_id)
            .where(PracticeDayRow.seconds >= MIN_SHOWN_SECONDS)
        )
        if scope == "everyone":
            query = query.where(UserRow.is_private.is_(False))
        else:
            followed = select(FollowRow.followed_id).where(
                FollowRow.follower_id == viewer_id, FollowRow.accepted.is_(True)
            )
            query = query.where(PracticeDayRow.user_id.in_(followed))
        if before is not None:
            query = query.where(PracticeDayRow.last_at < before)
        with self._db.session() as session:
            rows = session.execute(query.order_by(PracticeDayRow.last_at.desc()).limit(limit))
            return [
                FeedEntry(**_entry(row).model_dump(), username=username) for row, username in rows
            ]


def _entry(row: PracticeDayRow) -> PracticeEntry:
    return PracticeEntry(
        video_id=row.video_id,
        title=row.title,
        day=row.day,
        last_at=row.last_at,
        seconds=row.seconds,
    )
