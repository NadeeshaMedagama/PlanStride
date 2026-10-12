import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain import (
    INVITATION_TTL,
    ORG_ROLE_OWNER,
    InvitableRole,
    InvitationStatus,
    OrgRole,
    utcnow,
)
from app.exceptions import (
    ConflictException,
    ForbiddenException,
    InvalidStateException,
    ResourceNotFoundException,
)
from app.models import (
    Invitation,
    Membership,
    Organization,
    Team,
    TeamMembership,
    User,
)
from app.security import generate_invite_token, hash_invite_token
from app.tenancy import OrgAccess

INVALID_INVITE_MESSAGE = "This invite link is invalid or has expired."


@dataclass(frozen=True)
class TeamRef:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class MemberRow:
    membership: Membership
    user: User
    teams: list[TeamRef]


class OrganizationService:
    """Organizations, their members and roles, and invite links."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Organizations -----------------------------------------------------------

    async def create_organization(self, *, owner: User, name: str) -> Membership:
        """Create an organization with `owner` as its first owner."""
        organization = Organization(name=name)
        membership = Membership(
            organization=organization, user=owner, role=ORG_ROLE_OWNER
        )
        self.session.add_all([organization, membership])
        await self.session.flush()
        return membership

    async def list_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[tuple[Membership, Organization]]:
        rows = await self.session.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id == user_id)
            .order_by(Organization.name)
        )
        return rows.tuples().all()

    async def counts(self, organization_id: uuid.UUID) -> tuple[int, int]:
        """(member count, team count) for one organization."""
        members = await self.session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == organization_id)
        )
        teams = await self.session.scalar(
            select(func.count())
            .select_from(Team)
            .where(Team.organization_id == organization_id)
        )
        return members or 0, teams or 0

    async def rename(self, organization: Organization, name: str) -> Organization:
        organization.name = name
        await self.session.flush()
        return organization

    # --- Members -----------------------------------------------------------------

    async def list_members(
        self, organization_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> list[MemberRow]:
        member_query = (
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization_id)
            .order_by(User.first_name, User.last_name)
        )
        team_query = (
            select(TeamMembership.user_id, Team.id, Team.name)
            .join(Team, Team.id == TeamMembership.team_id)
            .where(TeamMembership.organization_id == organization_id)
            .order_by(Team.name)
        )
        if user_id is not None:
            member_query = member_query.where(Membership.user_id == user_id)
            team_query = team_query.where(TeamMembership.user_id == user_id)

        rows = (await self.session.execute(member_query)).tuples()
        team_rows = await self.session.execute(team_query)
        teams_by_user: dict[uuid.UUID, list[TeamRef]] = defaultdict(list)
        for member_id, team_id, team_name in team_rows.tuples():
            teams_by_user[member_id].append(TeamRef(id=team_id, name=team_name))

        return [
            MemberRow(membership=membership, user=user, teams=teams_by_user[user.id])
            for membership, user in rows
        ]

    async def get_member(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemberRow:
        rows = await self.list_members(organization_id, user_id=user_id)
        if not rows:
            raise ResourceNotFoundException("Member not found")
        return rows[0]

    async def get_membership(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> Membership:
        membership = await self.session.scalar(
            select(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
            .options(selectinload(Membership.user))
        )
        if membership is None:
            raise ResourceNotFoundException("Member not found")
        return membership

    async def change_role(
        self, access: OrgAccess, user_id: uuid.UUID, role: OrgRole
    ) -> Membership:
        """Change a member's role. Owners can do anything; admins can manage
        admins and members but can't touch owners or create new ones. An
        organization always keeps at least one owner."""
        await self._lock_organization(access.organization_id)
        target = await self.get_membership(access.organization_id, user_id)
        if target.role == role:
            return target

        self._ensure_can_manage(access, target)
        if role == ORG_ROLE_OWNER and not access.is_owner:
            raise ForbiddenException("Only an owner can make someone an owner.")
        if target.role == ORG_ROLE_OWNER:
            await self._ensure_not_last_owner(access.organization_id)

        target.role = role
        await self.session.flush()
        return target

    async def remove_member(self, access: OrgAccess, user_id: uuid.UUID) -> None:
        """Remove someone from the organization. Their team memberships go with
        them (database cascade) and any team they led loses its lead. Their past
        plans stay in the organization's history."""
        await self._lock_organization(access.organization_id)
        target = await self.get_membership(access.organization_id, user_id)
        self._ensure_can_manage(access, target)
        if target.role == ORG_ROLE_OWNER:
            await self._ensure_not_last_owner(access.organization_id)

        await self.session.execute(
            update(Team)
            .where(
                Team.organization_id == access.organization_id,
                Team.lead_user_id == user_id,
            )
            .values(lead_user_id=None)
        )
        await self.session.delete(target)
        await self.session.flush()

    def _ensure_can_manage(self, access: OrgAccess, target: Membership) -> None:
        if target.role == ORG_ROLE_OWNER and not access.is_owner:
            raise ForbiddenException("Only an owner can change or remove an owner.")

    async def _ensure_not_last_owner(self, organization_id: uuid.UUID) -> None:
        owners = await self.session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == ORG_ROLE_OWNER,
            )
        )
        if (owners or 0) <= 1:
            raise InvalidStateException(
                "An organization needs at least one owner. Make someone else an "
                "owner first."
            )

    async def _lock_organization(self, organization_id: uuid.UUID) -> None:
        # Serializes role changes within one organization, so two concurrent
        # demotions can't both pass the "last owner" check.
        await self.session.execute(
            select(Organization.id)
            .where(Organization.id == organization_id)
            .with_for_update()
        )

    # --- Invitations ---------------------------------------------------------------

    async def create_invitation(
        self, access: OrgAccess, role: InvitableRole
    ) -> tuple[Invitation, str]:
        """Create an invite link. Returns the invitation and its raw token; the
        token is not stored and can't be shown again."""
        token = generate_invite_token()
        invitation = Invitation(
            organization_id=access.organization_id,
            created_by=access.user,
            accepted_by=None,
            role=role,
            token_hash=hash_invite_token(token),
            expires_at=utcnow() + INVITATION_TTL,
        )
        self.session.add(invitation)
        await self.session.flush()
        return invitation, token

    async def list_invitations(
        self, organization_id: uuid.UUID
    ) -> Sequence[Invitation]:
        result = await self.session.execute(
            select(Invitation)
            .where(Invitation.organization_id == organization_id)
            .options(
                selectinload(Invitation.created_by),
                selectinload(Invitation.accepted_by),
            )
            .order_by(Invitation.created_at.desc())
            .limit(50)
        )
        return result.scalars().all()

    async def revoke_invitation(
        self, organization_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> Invitation:
        invitation = await self.session.scalar(
            select(Invitation)
            .where(
                Invitation.id == invitation_id,
                Invitation.organization_id == organization_id,
            )
            .options(
                selectinload(Invitation.created_by),
                selectinload(Invitation.accepted_by),
            )
        )
        if invitation is None:
            raise ResourceNotFoundException("Invitation not found")
        if invitation.accepted_at is not None:
            raise InvalidStateException("This invitation has already been used.")
        if invitation.revoked_at is None:
            invitation.revoked_at = utcnow()
            await self.session.flush()
        return invitation

    async def get_valid_invitation(
        self, token: str, *, for_update: bool = False
    ) -> Invitation:
        """Resolve an invite token, or 404 if it is unknown, used, revoked or
        expired (one message for all, so tokens can't be probed). A suspended
        organization's invites are refused with 403."""
        stmt = (
            select(Invitation)
            .where(Invitation.token_hash == hash_invite_token(token))
            .options(
                selectinload(Invitation.organization),
                selectinload(Invitation.created_by),
            )
        )
        if for_update:
            # Locks the invitation row so two people can't accept it at once.
            stmt = stmt.with_for_update(of=Invitation)
        invitation = await self.session.scalar(stmt)
        if (
            invitation is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at <= utcnow()
        ):
            raise ResourceNotFoundException(INVALID_INVITE_MESSAGE)
        if invitation.organization.is_suspended:
            raise ForbiddenException(
                "This organization is currently suspended, so it can't take new "
                "members.",
                code="ORGANIZATION_SUSPENDED",
            )
        return invitation

    async def accept_invitation(self, user: User, token: str) -> Membership:
        invitation = await self.get_valid_invitation(token, for_update=True)
        existing = await self.session.scalar(
            select(Membership.id).where(
                Membership.organization_id == invitation.organization_id,
                Membership.user_id == user.id,
            )
        )
        if existing is not None:
            raise ConflictException(
                f"You're already a member of {invitation.organization.name}."
            )
        return await self.join_with_invitation(user, invitation)

    async def join_with_invitation(
        self, user: User, invitation: Invitation
    ) -> Membership:
        membership = Membership(
            organization=invitation.organization, user=user, role=invitation.role
        )
        invitation.accepted_at = utcnow()
        invitation.accepted_by = user
        self.session.add(membership)
        await self.session.flush()
        return membership


def invitation_status(invitation: Invitation) -> InvitationStatus:
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.expires_at <= utcnow():
        return "expired"
    return "pending"
