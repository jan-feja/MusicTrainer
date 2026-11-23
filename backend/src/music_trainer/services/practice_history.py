"""What users practiced: one entry per user, song and day, with the time the music played,
and one entry per preset they made.

The player reports the playing time in small parts; they add up in the day's
entry, so opening a song ten times a day is still one entry. Entries under
MIN_SHOWN_SECONDS (a song opened and left) are kept but not shown.

A preset keeps its entry while it exists: renaming it renames the entry,
deleting it removes the entry.

The feed lists the newest entries of public profiles, or of the users one follows.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal, TypeVar

from sqlalchemy import Select, delete, func, select

from music_trainer.db import Database, FollowRow, PracticeDayRow, PresetMadeRow, UserRow
from music_trainer.models import FeedEntry, PracticeEntry, Preset
from music_trainer.services.accounts import utc_now

MIN_SHOWN_SECONDS = 30
FeedScope = Literal["everyone", "following"]
_Entry = TypeVar("_Entry", bound=PracticeEntry)


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

    def presets_changed(
        self, user_id: int, video_id: str, title: str, before: list[Preset], after: list[Preset]
    ) -> None:
        """The user changed their presets of the song: new ones get an entry, renamed
        ones rename theirs, deleted ones lose it."""
        known = {preset.id for preset in before}
        names = {preset.id: preset.name for preset in after}
        now = self._clock()
        with self._db.session() as session, session.begin():
            mine = (PresetMadeRow.user_id == user_id, PresetMadeRow.video_id == video_id)
            session.execute(
                delete(PresetMadeRow).where(*mine, PresetMadeRow.preset_id.not_in(names))
            )
            for row in session.scalars(select(PresetMadeRow).where(*mine)):
                row.name = names[row.preset_id]
            for preset in after:
                if (
                    preset.id not in known
                    and session.get(PresetMadeRow, (user_id, video_id, preset.id)) is None
                ):
                    session.add(
                        PresetMadeRow(
                            user_id=user_id,
                            video_id=video_id,
                            preset_id=preset.id,
                            name=preset.name,
                            title=title,
                            created_at=now,
                        )
                    )

    def history(
        self, user_id: int, limit: int, before: datetime | None = None
    ) -> list[PracticeEntry]:
        """The user's entries, newest first; `before` continues an earlier page."""
        practice, presets = _queries(before)
        with self._db.session() as session:
            practiced = session.scalars(
                practice.where(PracticeDayRow.user_id == user_id).limit(limit)
            )
            made = session.scalars(presets.where(PresetMadeRow.user_id == user_id).limit(limit))
            entries = [*map(_practiced, practiced), *map(_made, made)]
        return _newest(entries, limit)

    def today_seconds(self, user_id: int) -> int:
        """How long the music played for the user today (UTC, as the entries' days)."""
        with self._db.session() as session:
            total = session.scalar(
                select(func.sum(PracticeDayRow.seconds)).where(
                    PracticeDayRow.user_id == user_id, PracticeDayRow.day == self._clock().date()
                )
            )
            return int(total or 0)

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
        practice, presets = _queries(before)

        def visible(query: Select, user_column: object) -> Select:  # type: ignore[type-arg]
            query = query.add_columns(UserRow.username).join(UserRow, UserRow.id == user_column)
            if scope == "everyone":
                return query.where(UserRow.is_private.is_(False))
            followed = select(FollowRow.followed_id).where(
                FollowRow.follower_id == viewer_id, FollowRow.accepted.is_(True)
            )
            return query.where(user_column.in_(followed))  # type: ignore[attr-defined]

        with self._db.session() as session:
            practiced = session.execute(visible(practice, PracticeDayRow.user_id).limit(limit))
            made = session.execute(visible(presets, PresetMadeRow.user_id).limit(limit))
            entries = [
                *(
                    FeedEntry(**_practiced(row).model_dump(), username=name)
                    for row, name in practiced
                ),
                *(FeedEntry(**_made(row).model_dump(), username=name) for row, name in made),
            ]
        return _newest(entries, limit)


def _queries(before: datetime | None) -> tuple[Select, Select]:  # type: ignore[type-arg]
    """The shown practice days and the presets made, newest first (before `before`)."""
    practice = select(PracticeDayRow).where(PracticeDayRow.seconds >= MIN_SHOWN_SECONDS)
    presets = select(PresetMadeRow)
    if before is not None:
        practice = practice.where(PracticeDayRow.last_at < before)
        presets = presets.where(PresetMadeRow.created_at < before)
    return (
        practice.order_by(PracticeDayRow.last_at.desc()),
        presets.order_by(PresetMadeRow.created_at.desc()),
    )


def _newest(entries: list[_Entry], limit: int) -> list[_Entry]:
    return sorted(entries, key=lambda entry: entry.last_at, reverse=True)[:limit]


def _practiced(row: PracticeDayRow) -> PracticeEntry:
    return PracticeEntry(
        video_id=row.video_id,
        title=row.title,
        day=row.day,
        last_at=row.last_at,
        seconds=row.seconds,
    )


def _made(row: PresetMadeRow) -> PracticeEntry:
    return PracticeEntry(
        kind="preset",
        video_id=row.video_id,
        title=row.title,
        day=row.created_at.date(),
        last_at=row.created_at,
        seconds=0,
        preset=row.name,
    )
