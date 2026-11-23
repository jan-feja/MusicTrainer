"""User accounts and their login sessions.

Passwords are hashed with argon2. A login session is a random token in a cookie;
the database keeps only its SHA-256 hash, so a copy of the database logs no one in.
"""

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select

from music_trainer.db import Database, SessionRow, UserRow
from music_trainer.models import User


class AccountError(Exception):
    pass


class UsernameTakenError(AccountError):
    def __init__(self, username: str) -> None:
        super().__init__(f"The username {username} is taken")


class WrongPasswordError(AccountError):
    def __init__(self) -> None:
        super().__init__("Wrong password")


def utc_now() -> datetime:
    return datetime.now(UTC)


class Accounts:
    def __init__(
        self,
        db: Database,
        session_lifetime: timedelta,
        clock: Callable[[], datetime] = utc_now,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self._db = db
        self._session_lifetime = session_lifetime
        self._clock = clock
        self._hasher = hasher or PasswordHasher()
        # compared against when the username is unknown, so that takes as long as a wrong password
        self._dummy_hash = self._hasher.hash(secrets.token_hex(16))

    def register(self, username: str, password: str) -> User:
        """Create an account. The username's format is checked by the API model."""
        with self._db.session() as session, session.begin():
            key = username.lower()
            if session.scalar(select(UserRow.id).where(UserRow.username_key == key)) is not None:
                raise UsernameTakenError(username)
            row = UserRow(
                username=username,
                username_key=key,
                password_hash=self._hasher.hash(password),
                created_at=self._clock(),
            )
            session.add(row)
            session.flush()
            return _user(row)

    def authenticate(self, username: str, password: str) -> User | None:
        """The account, if the username (any case) and password match."""
        with self._db.session() as session:
            row = session.scalar(select(UserRow).where(UserRow.username_key == username.lower()))
            if row is None:
                self._matches(self._dummy_hash, password)
                return None
            return _user(row) if self._matches(row.password_hash, password) else None

    def get_user(self, user_id: int) -> User | None:
        with self._db.session() as session:
            row = session.get(UserRow, user_id)
            return _user(row) if row else None

    def change_password(self, user_id: int, current: str, new: str, keep_token: str) -> None:
        """Set a new password; logs out every other session of the user."""
        with self._db.session() as session, session.begin():
            row = session.get(UserRow, user_id)
            if row is None or not self._matches(row.password_hash, current):
                raise WrongPasswordError()
            row.password_hash = self._hasher.hash(new)
            session.execute(
                delete(SessionRow).where(
                    SessionRow.user_id == user_id, SessionRow.token_hash != _hash_token(keep_token)
                )
            )

    def delete_account(self, user_id: int, password: str) -> None:
        """Delete the user with their sessions and library entries (not the songs' files)."""
        with self._db.session() as session, session.begin():
            row = session.get(UserRow, user_id)
            if row is None or not self._matches(row.password_hash, password):
                raise WrongPasswordError()
            session.delete(row)  # the database cascades to sessions and library entries

    def create_session(self, user_id: int) -> str:
        """Log the user in; returns the token for the cookie."""
        token = secrets.token_urlsafe(32)
        now = self._clock()
        with self._db.session() as session, session.begin():
            session.execute(delete(SessionRow).where(SessionRow.expires_at <= now))
            session.add(
                SessionRow(
                    token_hash=_hash_token(token),
                    user_id=user_id,
                    created_at=now,
                    expires_at=now + self._session_lifetime,
                )
            )
        return token

    def user_for_token(self, token: str) -> User | None:
        """The logged-in user, or None if the token is unknown or has expired.

        A session in use is extended once half its lifetime has passed.
        """
        now = self._clock()
        with self._db.session() as session, session.begin():
            row = session.get(SessionRow, _hash_token(token))
            if row is None or row.expires_at <= now:
                return None
            if row.expires_at - now < self._session_lifetime / 2:
                row.expires_at = now + self._session_lifetime
            user = session.get(UserRow, row.user_id)
            return _user(user) if user else None

    def end_session(self, token: str) -> None:
        with self._db.session() as session, session.begin():
            session.execute(delete(SessionRow).where(SessionRow.token_hash == _hash_token(token)))

    def _matches(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user(row: UserRow) -> User:
    return User(id=row.id, username=row.username)
