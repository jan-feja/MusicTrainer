"""The SQLite database: user accounts, their sessions, and who has which song.

Songs and their analysis stay on disk (see services/library.py). The database
holds each user's library: the songs in it, with the user's own presets and
player settings for each. Guests have no rows; their library lives in the browser.

    users            accounts (username + argon2 password hash)
    sessions         logged-in browsers: the hash of the cookie's token
    library_entries  (user, song): the user's presets and player settings for it
    songs            per song: when a guest last used it (songs nobody has are deleted)
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
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


class SongRow(Base):
    __tablename__ = "songs"

    video_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_guest_use_at: Mapped[datetime | None]
    """When a guest last downloaded or opened the song."""


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
    columns = {column["name"] for column in inspect(engine).get_columns("library_entries")}
    if "loops_json" in columns:  # saved loops became presets (a saved loop is a valid preset)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE library_entries RENAME COLUMN loops_json TO presets_json")
            )


def _configure_connection(connection: object, _record: object) -> None:
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys = ON")  # SQLite ignores ON DELETE CASCADE otherwise
    cursor.close()
