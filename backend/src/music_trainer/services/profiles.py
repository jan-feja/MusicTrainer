"""Users' profiles: description, privacy, who follows whom, and the notifications about it.

Following a public profile takes effect at once; following a private one is a
request its owner accepts or declines. Only accepted followers (and the owner)
see a private profile's songs and history.

Notifications are read from the follows themselves: requests waiting for the
user, new followers, and accepted requests the user sent. Taking a follow
back takes its notification with it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update

from music_trainer.db import Database, FollowRow, UserRow
from music_trainer.models import (
    FollowState,
    Notification,
    NotificationKind,
    Notifications,
    ProfileSettings,
    UserSummary,
)
from music_trainer.services.accounts import utc_now


@dataclass(frozen=True)
class ProfileOwner:
    """A user as their profile shows them."""

    id: int
    username: str
    description: str
    is_private: bool
    joined_at: datetime


class Profiles:
    def __init__(self, db: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def find(self, username: str) -> ProfileOwner | None:
        """The user with that username, in any case."""
        with self._db.session() as session:
            row = session.scalar(select(UserRow).where(UserRow.username_key == username.lower()))
            return _owner(row) if row else None

    def settings(self, user_id: int) -> ProfileSettings:
        with self._db.session() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                return ProfileSettings()
            return ProfileSettings(description=row.description, is_private=row.is_private)

    def update_settings(self, user_id: int, settings: ProfileSettings) -> None:
        """Making a profile public accepts the follow requests waiting for it."""
        with self._db.session() as session, session.begin():
            row = session.get(UserRow, user_id)
            if row is None:
                return
            row.description = settings.description.strip()
            row.is_private = settings.is_private
            if not settings.is_private:
                session.execute(
                    update(FollowRow)
                    .where(FollowRow.followed_id == user_id, FollowRow.accepted.is_(False))
                    .values(accepted=True, accepted_at=self._clock())
                )

    def follow_state(self, viewer_id: int | None, owner: ProfileOwner) -> FollowState:
        if viewer_id is None:
            return "none"
        if viewer_id == owner.id:
            return "self"
        with self._db.session() as session:
            row = session.get(FollowRow, (viewer_id, owner.id))
        if row is None:
            return "none"
        return "following" if row.accepted else "requested"

    def can_view(self, viewer_id: int | None, owner: ProfileOwner) -> bool:
        """The viewer may see the owner's songs and history."""
        return not owner.is_private or self.follow_state(viewer_id, owner) in ("self", "following")

    def follow(self, follower_id: int, owner: ProfileOwner) -> FollowState:
        """Follow, or ask to follow a private profile; nothing changes if done already."""
        if follower_id == owner.id:
            return "self"
        with self._db.session() as session, session.begin():
            row = session.get(FollowRow, (follower_id, owner.id))
            if row is None:
                now = self._clock()
                row = FollowRow(
                    follower_id=follower_id,
                    followed_id=owner.id,
                    accepted=not owner.is_private,
                    created_at=now,
                    accepted_at=None if owner.is_private else now,
                )
                session.add(row)
            return "following" if row.accepted else "requested"

    def unfollow(self, follower_id: int, followed_id: int) -> bool:
        """Stop following, take back a request, or (the other way round) remove a follower
        or decline their request. Returns False if there was nothing to remove."""
        with self._db.session() as session, session.begin():
            result = session.execute(
                delete(FollowRow).where(
                    FollowRow.follower_id == follower_id, FollowRow.followed_id == followed_id
                )
            )
            return result.rowcount > 0  # type: ignore[attr-defined]

    def accept(self, user_id: int, follower_id: int) -> bool:
        """Accept a follow request; returns False if there was none."""
        with self._db.session() as session, session.begin():
            row = session.get(FollowRow, (follower_id, user_id))
            if row is None:
                return False
            if not row.accepted:
                row.accepted = True
                row.accepted_at = self._clock()
            return True

    def counts(self, user_id: int) -> tuple[int, int]:
        """(followers, following)."""
        with self._db.session() as session:

            def count(*conditions: object) -> int:
                return (
                    session.scalar(select(func.count()).select_from(FollowRow).where(*conditions))
                    or 0
                )

            return (
                count(FollowRow.followed_id == user_id, FollowRow.accepted.is_(True)),
                count(FollowRow.follower_id == user_id, FollowRow.accepted.is_(True)),
            )

    def followers(self, user_id: int) -> list[UserSummary]:
        """Who follows the user, newest first."""
        return self._users(
            FollowRow.follower_id,
            (FollowRow.followed_id == user_id, FollowRow.accepted.is_(True)),
        )

    def following(self, user_id: int) -> list[UserSummary]:
        """Whom the user follows, newest first."""
        return self._users(
            FollowRow.followed_id,
            (FollowRow.follower_id == user_id, FollowRow.accepted.is_(True)),
        )

    def notifications(self, user_id: int, limit: int = 50) -> Notifications:
        """Follow requests first (they wait for an answer), then the rest, newest first."""
        with self._db.session() as session:
            user = session.get(UserRow, user_id)
            seen_at = user.notifications_seen_at if user else None
            to_me = session.execute(
                select(FollowRow, UserRow)
                .join(UserRow, UserRow.id == FollowRow.follower_id)
                .where(FollowRow.followed_id == user_id)
            ).all()
            accepted_mine = session.execute(
                select(FollowRow, UserRow)
                .join(UserRow, UserRow.id == FollowRow.followed_id)
                .where(
                    FollowRow.follower_id == user_id,
                    FollowRow.accepted.is_(True),
                    FollowRow.accepted_at > FollowRow.created_at,  # it was a request
                )
            ).all()
            my_follows = {
                row.followed_id: row.accepted
                for row in session.scalars(
                    select(FollowRow).where(FollowRow.follower_id == user_id)
                )
            }

        def state(other_id: int) -> FollowState:
            if other_id not in my_follows:
                return "none"
            return "following" if my_follows[other_id] else "requested"

        def item(kind: NotificationKind, other: UserRow, at: datetime) -> Notification:
            return Notification(
                kind=kind,
                username=other.username,
                at=at,
                unread=seen_at is None or at > seen_at,
                follow_state=state(other.id),
            )

        items = [
            item("follow_request" if not row.accepted else "new_follower", other, row.created_at)
            for row, other in to_me
        ]
        items += [
            item("request_accepted", other, row.accepted_at)
            for row, other in accepted_mine
            if row.accepted_at is not None
        ]
        items.sort(key=lambda n: (n.kind != "follow_request", -n.at.timestamp()))
        return Notifications(
            items=items[:limit], unread=sum(1 for notification in items if notification.unread)
        )

    def mark_notifications_seen(self, user_id: int) -> None:
        with self._db.session() as session, session.begin():
            user = session.get(UserRow, user_id)
            if user is not None:
                user.notifications_seen_at = self._clock()

    def _users(self, column: object, conditions: tuple[object, ...]) -> list[UserSummary]:
        with self._db.session() as session:
            rows = session.scalars(
                select(UserRow)
                .join(FollowRow, UserRow.id == column)
                .where(*conditions)
                .order_by(FollowRow.created_at.desc())
            )
            return [UserSummary(username=row.username, description=row.description) for row in rows]


def _owner(row: UserRow) -> ProfileOwner:
    return ProfileOwner(
        id=row.id,
        username=row.username,
        description=row.description,
        is_private=row.is_private,
        joined_at=row.created_at,
    )
