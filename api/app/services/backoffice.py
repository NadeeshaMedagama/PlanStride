"""Read models and controls for PlanStride's own staff (internal console).

Data-minimization rule for everything in this module: staff see who belongs
where and how much the product is used, never what customers wrote. No query
here selects plan or task text, review comments or outcome notes, and the AI
usage log stores no content to begin with.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import ORG_ROLE_OWNER, OrgRole, current_week_start, utcnow
from app.exceptions import InvalidStateException, ResourceNotFoundException
from app.models import (
    AIUsageEvent,
    Membership,
    Organization,
    PlanTask,
    Team,
    TeamMembership,
    User,
    WeeklyPlan,
)
from app.services.search import LIKE_ESCAPE, contains_pattern

OrganizationStatusFilter = Literal["active", "suspended"]


@dataclass(frozen=True)
class OrganizationStats:
    organization: Organization
    member_count: int
    team_count: int
    plan_count: int
    last_active_at: datetime
    owners: list[User]


@dataclass(frozen=True)
class OrganizationMemberRow:
    user: User
    role: OrgRole
    joined_at: datetime


@dataclass(frozen=True)
class OrganizationTeamRow:
    id: uuid.UUID
    name: str
    member_count: int
    lead: User | None


@dataclass(frozen=True)
class OrganizationDetail:
    stats: OrganizationStats
    members: list[OrganizationMemberRow]
    teams: list[OrganizationTeamRow]
    plans_by_status: dict[str, int]


@dataclass(frozen=True)
class Overview:
    organizations: int
    organizations_suspended: int
    users: int
    users_deactivated: int
    staff: int
    plans_this_week: int
    plans_submitted_this_week: int
    ai_calls_24h: int
    ai_failed_24h: int
    ai_rate_limited_24h: int


def _member_count() -> ColumnElement[int]:
    return (
        select(func.count())
        .select_from(Membership)
        .where(Membership.organization_id == Organization.id)
        .scalar_subquery()
    )


def _team_count() -> ColumnElement[int]:
    return (
        select(func.count())
        .select_from(Team)
        .where(Team.organization_id == Organization.id)
        .scalar_subquery()
    )


def _plan_count() -> ColumnElement[int]:
    return (
        select(func.count())
        .select_from(WeeklyPlan)
        .where(WeeklyPlan.organization_id == Organization.id)
        .scalar_subquery()
    )


def _last_active_at() -> ColumnElement[datetime]:
    """The latest moment anyone did something in the organization: a plan or
    task written or changed, an AI call, or someone joining. Derived from the
    data itself, so there is no counter to keep in sync."""
    plans = (
        select(func.max(func.greatest(WeeklyPlan.created_at, WeeklyPlan.updated_at)))
        .where(WeeklyPlan.organization_id == Organization.id)
        .scalar_subquery()
    )
    tasks = (
        select(func.max(func.greatest(PlanTask.created_at, PlanTask.updated_at)))
        .join(WeeklyPlan, WeeklyPlan.id == PlanTask.plan_id)
        .where(WeeklyPlan.organization_id == Organization.id)
        .scalar_subquery()
    )
    ai_calls = (
        select(func.max(AIUsageEvent.created_at))
        .where(AIUsageEvent.organization_id == Organization.id)
        .scalar_subquery()
    )
    joins = (
        select(func.max(Membership.created_at))
        .where(Membership.organization_id == Organization.id)
        .scalar_subquery()
    )
    # GREATEST ignores NULLs, so an organization with no plans yet still
    # gets a value (at worst its creation time).
    return func.greatest(Organization.created_at, plans, tasks, ai_calls, joins)


class BackofficeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_organizations(
        self,
        *,
        search: str | None,
        status: OrganizationStatusFilter | None,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationStats], int]:
        conditions: list[ColumnElement[bool]] = []
        if search:
            conditions.append(
                Organization.name.ilike(contains_pattern(search), escape=LIKE_ESCAPE)
            )
        if status == "suspended":
            conditions.append(Organization.suspended_at.is_not(None))
        elif status == "active":
            conditions.append(Organization.suspended_at.is_(None))

        total = await self.session.scalar(
            select(func.count()).select_from(Organization).where(*conditions)
        )
        last_active = _last_active_at().label("last_active_at")
        rows = (
            (
                await self.session.execute(
                    select(
                        Organization,
                        _member_count(),
                        _team_count(),
                        _plan_count(),
                        last_active,
                    )
                    .where(*conditions)
                    .order_by(last_active.desc(), Organization.name)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .tuples()
            .all()
        )

        owners = await self._owners_by_organization([row[0].id for row in rows])
        return [
            OrganizationStats(
                organization=organization,
                member_count=members,
                team_count=teams,
                plan_count=plans,
                last_active_at=last_active_at,
                owners=owners[organization.id],
            )
            for organization, members, teams, plans, last_active_at in rows
        ], total or 0

    async def get_organization(self, organization_id: uuid.UUID) -> OrganizationDetail:
        row = (
            (
                await self.session.execute(
                    select(
                        Organization,
                        _member_count(),
                        _team_count(),
                        _plan_count(),
                        _last_active_at(),
                    ).where(Organization.id == organization_id)
                )
            )
            .tuples()
            .first()
        )
        if row is None:
            raise ResourceNotFoundException("Organization not found")
        organization, members, teams, plans, last_active_at = row
        owners = await self._owners_by_organization([organization.id])

        member_rows = await self.session.execute(
            select(User, Membership.role, Membership.created_at)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == organization.id)
            .order_by(User.first_name, User.last_name)
        )
        seat_counts = (
            select(TeamMembership.team_id, func.count().label("seats"))
            .where(TeamMembership.organization_id == organization.id)
            .group_by(TeamMembership.team_id)
            .subquery()
        )
        team_rows = await self.session.execute(
            select(Team.id, Team.name, func.coalesce(seat_counts.c.seats, 0), User)
            .outerjoin(seat_counts, seat_counts.c.team_id == Team.id)
            .outerjoin(User, User.id == Team.lead_user_id)
            .where(Team.organization_id == organization.id)
            .order_by(Team.name)
        )
        status_rows = await self.session.execute(
            select(WeeklyPlan.status, func.count())
            .where(WeeklyPlan.organization_id == organization.id)
            .group_by(WeeklyPlan.status)
        )

        return OrganizationDetail(
            stats=OrganizationStats(
                organization=organization,
                member_count=members,
                team_count=teams,
                plan_count=plans,
                last_active_at=last_active_at,
                owners=owners[organization.id],
            ),
            members=[
                OrganizationMemberRow(user=user, role=role, joined_at=joined_at)
                for user, role, joined_at in member_rows.tuples()
            ],
            teams=[
                OrganizationTeamRow(
                    id=team_id, name=name, member_count=seats, lead=lead
                )
                for team_id, name, seats, lead in team_rows.tuples()
            ],
            plans_by_status=dict(status_rows.tuples().all()),
        )

    async def suspend(
        self, organization_id: uuid.UUID, reason: str | None
    ) -> Organization:
        organization = await self._get(organization_id)
        if organization.is_suspended:
            raise InvalidStateException("This organization is already suspended.")
        organization.suspended_at = utcnow()
        organization.suspension_reason = reason or None
        await self.session.flush()
        return organization

    async def reinstate(self, organization_id: uuid.UUID) -> Organization:
        organization = await self._get(organization_id)
        if not organization.is_suspended:
            raise InvalidStateException("This organization isn't suspended.")
        organization.suspended_at = None
        organization.suspension_reason = None
        await self.session.flush()
        return organization

    async def overview(self) -> Overview:
        week = current_week_start()
        since = utcnow() - timedelta(hours=24)
        org_row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(Organization.suspended_at.is_not(None)),
                ).select_from(Organization)
            )
        ).one()
        user_row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(User.is_active.is_(False)),
                    func.count().filter(User.is_platform_staff.is_(True)),
                ).select_from(User)
            )
        ).one()
        plan_row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(WeeklyPlan.status != "draft"),
                ).where(WeeklyPlan.week_start == week)
            )
        ).one()
        ai_row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(AIUsageEvent.outcome == "failed"),
                    func.count().filter(AIUsageEvent.outcome == "rate_limited"),
                ).where(AIUsageEvent.created_at >= since)
            )
        ).one()
        return Overview(
            organizations=org_row[0],
            organizations_suspended=org_row[1],
            users=user_row[0],
            users_deactivated=user_row[1],
            staff=user_row[2],
            plans_this_week=plan_row[0],
            plans_submitted_this_week=plan_row[1],
            ai_calls_24h=ai_row[0],
            ai_failed_24h=ai_row[1],
            ai_rate_limited_24h=ai_row[2],
        )

    async def _get(self, organization_id: uuid.UUID) -> Organization:
        organization = await self.session.get(Organization, organization_id)
        if organization is None:
            raise ResourceNotFoundException("Organization not found")
        return organization

    async def _owners_by_organization(
        self, organization_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[User]]:
        owners: dict[uuid.UUID, list[User]] = defaultdict(list)
        if not organization_ids:
            return owners
        rows = await self.session.execute(
            select(Membership.organization_id, User)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.organization_id.in_(organization_ids),
                Membership.role == ORG_ROLE_OWNER,
            )
            .order_by(User.first_name)
        )
        for organization_id, user in rows.tuples():
            owners[organization_id].append(user)
        return owners
