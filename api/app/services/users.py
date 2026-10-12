import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import OrgRole
from app.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models import Membership, Organization, User
from app.security import hash_password
from app.services.search import LIKE_ESCAPE, contains_pattern


@dataclass(frozen=True)
class UserMembership:
    """One organization a user belongs to, as staff see it."""

    organization_id: uuid.UUID
    organization_name: str
    role: OrgRole
    is_suspended: bool


class UserService:
    """Business logic for user records.

    Holds the DB session so callers pass it once and then issue user operations
    without threading the session through every call.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_users(
        self,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[User], int]:
        """Return a page of users, newest first, optionally filtered by a
        case-insensitive match on name or email.

        Returns the page of users together with the total matching count so
        callers can render pagination controls without a second query
        round-trip on the caller side.
        """
        stmt = select(User)
        if search:
            pattern = contains_pattern(search)
            full_name = User.first_name + " " + User.last_name
            stmt = stmt.where(
                or_(
                    User.email.ilike(pattern, escape=LIKE_ESCAPE),
                    full_name.ilike(pattern, escape=LIKE_ESCAPE),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.session.execute(
            stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return result.scalars().all(), total or 0

    async def memberships_for(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[UserMembership]]:
        """The organizations each of `user_ids` belongs to, keyed by user id."""
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(Membership.user_id, Membership.role, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id.in_(user_ids))
            .order_by(Organization.name)
        )
        memberships: dict[uuid.UUID, list[UserMembership]] = defaultdict(list)
        for user_id, role, organization in rows.tuples():
            memberships[user_id].append(
                UserMembership(
                    organization_id=organization.id,
                    organization_name=organization.name,
                    role=role,
                    is_suspended=organization.is_suspended,
                )
            )
        return memberships

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Return a single user or raise 404."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            raise ResourceNotFoundException("User not found")
        return user

    async def create_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str | None = None,
        is_platform_staff: bool = False,
        is_active: bool = True,
    ) -> User:
        """Create a user, rejecting a duplicate email with 409."""
        email = email.lower()
        await self._ensure_email_available(email)

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hash_password(password) if password else None,
            is_platform_staff=is_platform_staff,
            is_active=is_active,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(
        self,
        user_id: uuid.UUID,
        changes: dict[str, Any],
        *,
        acting_user_id: uuid.UUID | None = None,
    ) -> User:
        """Apply a partial (PATCH) update to a user.

        Only keys present in `changes` are touched. A null for any column is
        treated as "leave unchanged" so a non-nullable field is never blanked.
        Password is intentionally not updatable here — use `change_password`.
        Staff access is never changed here either: it is granted only with
        `manage.py create-user --admin`, a deliberate operator action.
        """
        changes.pop("password", None)
        changes.pop("is_platform_staff", None)
        user = await self.get_user(user_id)

        if changes.get("is_active") is False and user.id == acting_user_id:
            raise ValidationException(
                "You can't deactivate your own account.", field="is_active"
            )

        if changes.get("email") is not None:
            email = changes["email"].lower()
            changes["email"] = email
            if email != user.email:
                await self._ensure_email_available(email, exclude_id=user.id)

        for field, value in changes.items():
            if value is not None:
                setattr(user, field, value)

        await self.session.flush()
        return user

    async def change_password(self, user_id: uuid.UUID, password: str) -> User:
        """Set a user's password (admin action, no current-password check)."""
        user = await self.get_user(user_id)
        user.password = hash_password(password)
        await self.session.flush()
        return user

    async def _ensure_email_available(
        self, email: str, *, exclude_id: uuid.UUID | None = None
    ) -> None:
        stmt = select(User.id).where(User.email == email)
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        if await self.session.scalar(stmt) is not None:
            raise ConflictException(
                f"User with email '{email}' already exists.", field="email"
            )
