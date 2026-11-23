"""Users' libraries: which songs each account has, with its own presets and player settings.

Also remembers when a guest last used a song: guests' libraries are in their
browsers, so that is all the server knows about them (see song_cleanup.py).
"""

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, func, select

from music_trainer.db import Database, FollowRow, LibraryEntryRow, SongRow, UserRow
from music_trainer.models import (
    FollowedPresets,
    GuestImportEntry,
    MyLibraryEntry,
    PlayerSettings,
    Preset,
)
from music_trainer.services.accounts import utc_now

logger = logging.getLogger(__name__)

_PRESET_LIST = TypeAdapter(list[Preset])
GUEST_USE_RESOLUTION = timedelta(hours=1)
"""A guest opening a song is written down at most this often."""


class UserLibrary:
    def __init__(self, db: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def video_ids(self, user_id: int, limit: int | None = None) -> list[str]:
        """The songs in the user's library, most recently added first."""
        with self._db.session() as session:
            return list(
                session.scalars(
                    select(LibraryEntryRow.video_id)
                    .where(LibraryEntryRow.user_id == user_id)
                    .order_by(LibraryEntryRow.added_at.desc())
                    .limit(limit)
                )
            )

    def count(self, user_id: int) -> int:
        with self._db.session() as session:
            return (
                session.scalar(select(func.count()).where(LibraryEntryRow.user_id == user_id)) or 0
            )

    def starred_ids(self, user_id: int) -> list[str]:
        """The user's starred songs, most recently starred first."""
        with self._db.session() as session:
            return list(
                session.scalars(
                    select(LibraryEntryRow.video_id)
                    .where(
                        LibraryEntryRow.user_id == user_id, LibraryEntryRow.starred_at.is_not(None)
                    )
                    .order_by(LibraryEntryRow.starred_at.desc())
                )
            )

    def entry(self, user_id: int, video_id: str) -> MyLibraryEntry | None:
        with self._db.session() as session:
            row = session.get(LibraryEntryRow, (user_id, video_id))
            if row is None:
                return None
            return MyLibraryEntry(
                video_id=video_id, added_at=row.added_at, starred=row.starred_at is not None
            )

    def set_starred(self, user_id: int, video_id: str, starred: bool) -> bool:
        """Star or unstar a song; returns False if it is not in the library."""
        with self._db.session() as session, session.begin():
            row = session.get(LibraryEntryRow, (user_id, video_id))
            if row is None:
                return False
            if starred and row.starred_at is None:
                row.starred_at = self._clock()
            elif not starred:
                row.starred_at = None
            return True

    def contains(self, user_id: int, video_id: str) -> bool:
        with self._db.session() as session:
            return session.get(LibraryEntryRow, (user_id, video_id)) is not None

    def add(self, user_id: int, video_id: str) -> None:
        """Add the song to the library; nothing happens if it is there already."""
        with self._db.session() as session, session.begin():
            if session.get(LibraryEntryRow, (user_id, video_id)) is None:
                session.add(_new_entry(user_id, video_id, self._clock()))

    def remove(self, user_id: int, video_id: str) -> bool:
        """Returns False if the song was not in the library."""
        with self._db.session() as session, session.begin():
            result = session.execute(
                delete(LibraryEntryRow).where(
                    LibraryEntryRow.user_id == user_id, LibraryEntryRow.video_id == video_id
                )
            )
            return result.rowcount > 0  # type: ignore[attr-defined]

    def read_presets(self, user_id: int, video_id: str) -> list[Preset] | None:
        """The user's presets of the song; None if the song is not in the library."""
        with self._db.session() as session:
            entry = session.get(LibraryEntryRow, (user_id, video_id))
            if entry is None:
                return None
            if entry.presets_json is None:
                return []
            try:
                return _PRESET_LIST.validate_json(entry.presets_json)
            except ValidationError as error:
                logger.warning("Ignoring unreadable presets of %s: %s", video_id, error)
                return []

    def write_presets(self, user_id: int, video_id: str, presets: list[Preset]) -> bool:
        """Returns False if the song is not in the library."""
        with self._db.session() as session, session.begin():
            entry = session.get(LibraryEntryRow, (user_id, video_id))
            if entry is None:
                return False
            entry.presets_json = _PRESET_LIST.dump_json(presets).decode()
            return True

    def followed_presets(self, user_id: int, video_id: str) -> list[FollowedPresets]:
        """The presets of the song made by the users the user follows, by username."""
        with self._db.session() as session:
            rows = session.execute(
                select(UserRow.username, LibraryEntryRow.presets_json)
                .join(UserRow, UserRow.id == LibraryEntryRow.user_id)
                .join(FollowRow, FollowRow.followed_id == LibraryEntryRow.user_id)
                .where(
                    FollowRow.follower_id == user_id,
                    FollowRow.accepted.is_(True),
                    LibraryEntryRow.video_id == video_id,
                    LibraryEntryRow.presets_json.is_not(None),
                )
                .order_by(UserRow.username_key)
            ).all()
        found = []
        for username, presets_json in rows:
            try:
                presets = _PRESET_LIST.validate_json(presets_json)
            except ValidationError:
                continue
            if presets:
                found.append(FollowedPresets(username=username, presets=presets))
        return found

    def read_settings(self, user_id: int, video_id: str) -> PlayerSettings | None:
        """How the user left the player (defaults if never opened); None if not in the library."""
        with self._db.session() as session:
            entry = session.get(LibraryEntryRow, (user_id, video_id))
            if entry is None:
                return None
            if entry.settings_json is None:
                return PlayerSettings()
            try:
                return PlayerSettings.model_validate_json(entry.settings_json)
            except ValidationError as error:
                logger.warning("Ignoring unreadable player settings of %s: %s", video_id, error)
                return PlayerSettings()

    def write_settings(self, user_id: int, video_id: str, settings: PlayerSettings) -> bool:
        """Returns False if the song is not in the library."""
        with self._db.session() as session, session.begin():
            entry = session.get(LibraryEntryRow, (user_id, video_id))
            if entry is None:
                return False
            entry.settings_json = settings.model_dump_json()
            return True

    def import_guest(self, user_id: int, entries: Iterable[GuestImportEntry]) -> None:
        """Add a guest's songs; their presets and settings are kept where the user has none."""
        now = self._clock()
        with self._db.session() as session, session.begin():
            for item in entries:
                entry = session.get(LibraryEntryRow, (user_id, item.video_id))
                if entry is None:
                    entry = _new_entry(user_id, item.video_id, now)
                    session.add(entry)
                if item.presets and entry.presets_json in (None, "[]"):
                    entry.presets_json = _PRESET_LIST.dump_json(item.presets).decode()
                if item.settings is not None and entry.settings_json is None:
                    entry.settings_json = item.settings.model_dump_json()

    def has_owner(self, video_id: str) -> bool:
        """Some account has the song in its library."""
        with self._db.session() as session:
            owner = session.scalar(
                select(LibraryEntryRow.user_id).where(LibraryEntryRow.video_id == video_id).limit(1)
            )
            return owner is not None

    def touch_guest_use(self, video_id: str) -> None:
        """A guest downloaded or opened the song."""
        now = self._clock()
        with self._db.session() as session, session.begin():
            song = session.get(SongRow, video_id)
            if song is None:
                session.add(SongRow(video_id=video_id, last_guest_use_at=now))
            elif song.last_guest_use_at is None or (
                now - song.last_guest_use_at >= GUEST_USE_RESOLUTION
            ):
                song.last_guest_use_at = now

    def last_guest_use(self, video_id: str) -> datetime | None:
        with self._db.session() as session:
            song = session.get(SongRow, video_id)
            return song.last_guest_use_at if song else None

    def forget_song(self, video_id: str) -> None:
        """The song's files were deleted: drop what is known about guests using it."""
        with self._db.session() as session, session.begin():
            session.execute(delete(SongRow).where(SongRow.video_id == video_id))


def _new_entry(user_id: int, video_id: str, now: datetime) -> LibraryEntryRow:
    return LibraryEntryRow(
        user_id=user_id,
        video_id=video_id,
        added_at=now,
        presets_json=None,
        settings_json=None,
        starred_at=None,
    )
