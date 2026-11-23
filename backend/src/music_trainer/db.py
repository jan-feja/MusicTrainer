"""The SQLite database: user accounts, their sessions, and who has which song.

Songs and their analysis stay on disk (see services/library.py). The database
holds each user's library: the songs in it, with the user's own presets and
player settings for each. Guests have no rows; their library lives in the browser.

    users            accounts (username + argon2 password hash, profile description, privacy)
    sessions         logged-in browsers: the hash of the cookie's token
    library_entries  (user, song): the user's presets and player settings for it, starred or not
    songs            per song: when a guest last used it (songs nobody has are deleted)
    follows          (follower, followed user): accepted, or a request to a private profile
    practice_days    (user, song, day): how long the user practiced the song that day
    presets_made     (user, song, preset): a preset the user made, for the history and the feed
    comments         what users wrote under a song; shown to everyone under the song
"""

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A timezone-aware UTC datetime; SQLite itself stores no time zone."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetimes stored in the database must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UtcDateTime}  # noqa: RUF012 (SQLAlchemy's convention)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    """As the user typed it; shown in the app."""
    username_key: Mapped[str] = mapped_column(String(30), unique=True)
    """Lower case: usernames are unique regardless of case."""
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime]
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    """Shown on the profile."""
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    """Only accepted followers see the profile's songs and history."""
    notifications_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    """When the user last opened their notifications; newer ones are unread."""


class SessionRow(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    """SHA-256 of the cookie's token; the token itself is never stored."""
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]


class LibraryEntryRow(Base):
    __tablename__ = "library_entries"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    added_at: Mapped[datetime]
    presets_json: Mapped[str | None] = mapped_column(Text)
    """The user's presets (a list of Preset); None: none saved yet."""
    settings_json: Mapped[str | None] = mapped_column(Text)
    """How the user left the player (PlayerSettings); None: never opened."""
    starred_at: Mapped[datetime | None]
    """When the user starred the song; None: not starred."""


class SongRow(Base):
    __tablename__ = "songs"

    video_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_guest_use_at: Mapped[datetime | None]
    """When a guest last downloaded or opened the song."""


class FollowRow(Base):
    __tablename__ = "follows"

    follower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followed_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    accepted: Mapped[bool] = mapped_column(Boolean)
    """False: a request to a private profile, waiting for its owner."""
    created_at: Mapped[datetime]
    """When the user followed, or asked to."""
    accepted_at: Mapped[datetime | None] = mapped_column(default=None)
    """When the follow took effect: `created_at` for a public profile, later for a request."""


class PracticeDayRow(Base):
    """One row per user, song and day (UTC): opening a song ten times is one entry."""

    __tablename__ = "practice_days"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    """Kept here: the history outlives the song's files."""
    last_at: Mapped[datetime] = mapped_column(index=True)
    """When the song was last played that day."""
    seconds: Mapped[int]
    """How long the music played."""


class PresetMadeRow(Base):
    """A preset a user made of a song: an entry of its own in the history and the feed."""

    __tablename__ = "presets_made"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    preset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    """Follows renames of the preset."""
    title: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(index=True)


class CommentRow(Base):
    """A comment under a song; everyone sees it there, whoever wrote it."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500))
    """The song's title, for the feed (comments outlive the song's files)."""
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(index=True)


class Database:
    """The database file; creates its tables when they are missing."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # route handlers run in a thread pool, and the cleanup in its own thread
        self._engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        event.listen(self._engine, "connect", _configure_connection)
        Base.metadata.create_all(self._engine)
        _migrate(self._engine)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def session(self) -> Session:
        """A new session; use it as `with db.session() as s, s.begin(): ...`."""
        return self._sessions()

    def close(self) -> None:
        self._engine.dispose()


def _migrate(engine: Engine) -> None:
    """Changes to tables made before (create_all only adds missing tables)."""
    inspector = inspect(engine)
    users = {column["name"] for column in inspector.get_columns("users")}
    entries = {column["name"] for column in inspector.get_columns("library_entries")}
    changes = []
    if "loops_json" in entries:  # saved loops became presets (a saved loop is a valid preset)
        changes.append("ALTER TABLE library_entries RENAME COLUMN loops_json TO presets_json")
    if "starred_at" not in entries:
        changes.append("ALTER TABLE library_entries ADD COLUMN starred_at DATETIME")
    if "description" not in users:
        changes.append("ALTER TABLE users ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "is_private" not in users:
        changes.append("ALTER TABLE users ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT 0")
    if "notifications_seen_at" not in users:
        changes.append("ALTER TABLE users ADD COLUMN notifications_seen_at DATETIME")
    follows = {column["name"] for column in inspector.get_columns("follows")}
    if "accepted_at" not in follows:
        changes.append("ALTER TABLE follows ADD COLUMN accepted_at DATETIME")
        changes.append("UPDATE follows SET accepted_at = created_at WHERE accepted")
    if changes:
        with engine.begin() as connection:
            for change in changes:
                connection.execute(text(change))


def _configure_connection(connection: object, _record: object) -> None:
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys = ON")  # SQLite ignores ON DELETE CASCADE otherwise
    cursor.close()
