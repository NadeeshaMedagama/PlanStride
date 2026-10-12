import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    ConflictException,
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models import Membership, Team, TeamMembership, User, WeeklyPlan
from app.services.plans import PlanService
from app.tenancy import OrgAccess


@dataclass(frozen=True)
class TeamRow:
    team: Team
    member_count: int
    is_member: bool
    is_lead: bool


@dataclass(frozen=True)
class TeamWeekRow:
    member: User
    is_lead: bool
    plan: WeeklyPlan | None


@dataclass(frozen=True)
class WeekStats:
    """How a team did in one week. Draft plans count as "planned" but their
    tasks stay out of the totals: a draft is still private to its author."""

    week_start: date
    members: int
    planned: int
    submitted: int
    approved: int
    done: int
    shipped: int
    tasks_done: int
    tasks_total: int


def summarize_week(
    week_start: date, member_count: int, plans: Sequence[WeeklyPlan]
) -> WeekStats:
    shared = [plan for plan in plans if plan.status != "draft"]
    return WeekStats(
        week_start=week_start,
        members=member_count,
        planned=len(plans),
        submitted=len(shared),
        approved=sum(plan.status in ("approved", "done") for plan in shared),
        done=sum(plan.status == "done" for plan in shared),
        shipped=sum(plan.main_task_shipped is True for plan in shared),
        tasks_done=sum(task.status == "done" for plan in shared for task in plan.tasks),
        tasks_total=sum(len(plan.tasks) for plan in shared),
    )


class TeamService:
    """Teams inside an organization: membership, leads and the team's week.

    Only organization owners and admins change teams. Anyone on a team, its
    lead, and the organization's owners and admins can see the team's week.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Reads -----------------------------------------------------------------

    async def list_teams(self, access: OrgAccess) -> list[TeamRow]:
        member_counts = (
            select(TeamMembership.team_id, func.count().label("member_count"))
            .where(TeamMembership.organization_id == access.organization_id)
            .group_by(TeamMembership.team_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(Team, func.coalesce(member_counts.c.member_count, 0))
            .outerjoin(member_counts, member_counts.c.team_id == Team.id)
            .where(Team.organization_id == access.organization_id)
            .options(selectinload(Team.lead))
            .order_by(Team.name)
        )
        my_team_ids = set(
            (
                await self.session.scalars(
                    select(TeamMembership.team_id).where(
                        TeamMembership.organization_id == access.organization_id,
                        TeamMembership.user_id == access.user_id,
                    )
                )
            ).all()
        )
        return [
            TeamRow(
                team=team,
                member_count=count,
                is_member=team.id in my_team_ids,
                is_lead=team.lead_user_id == access.user_id,
            )
            for team, count in rows.tuples()
        ]

    async def get_team(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> Team:
        team = await self.session.scalar(
            select(Team)
            .where(Team.id == team_id, Team.organization_id == organization_id)
            .options(selectinload(Team.lead))
            .execution_options(populate_existing=True)
        )
        if team is None:
            raise ResourceNotFoundException("Team not found")
        return team

    async def list_members(self, team_id: uuid.UUID) -> Sequence[User]:
        result = await self.session.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.team_id == team_id)
            .order_by(User.first_name, User.last_name)
        )
        return result.scalars().all()

    async def is_member(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        found = await self.session.scalar(
            select(TeamMembership.id).where(
                TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
            )
        )
        return found is not None

    async def can_view_week(self, access: OrgAccess, team: Team) -> bool:
        return (
            access.can_manage
            or team.lead_user_id == access.user_id
            or await self.is_member(team.id, access.user_id)
        )

    async def ensure_can_view_week(self, access: OrgAccess, team: Team) -> None:
        if not await self.can_view_week(access, team):
            raise ForbiddenException(
                "Only this team's members, its lead, and organization owners and "
                "admins can see the team's week."
            )

    async def team_week(
        self, access: OrgAccess, team: Team, week_start: date
    ) -> list[TeamWeekRow]:
        await self.ensure_can_view_week(access, team)
        members = await self.list_members(team.id)
        plans = await PlanService(self.session).plans_for_members(
            access.organization_id,
            [member.id for member in members],
            week_from=week_start,
            week_to=week_start,
        )
        plan_by_user = {plan.user_id: plan for plan in plans}
        return [
            TeamWeekRow(
                member=member,
                is_lead=member.id == team.lead_user_id,
                plan=plan_by_user.get(member.id),
            )
            for member in members
        ]

    async def team_history(
        self, access: OrgAccess, team: Team, *, last_week: date, weeks: int
    ) -> list[WeekStats]:
        """Week-by-week stats for the team's current members, newest first."""
        await self.ensure_can_view_week(access, team)
        members = await self.list_members(team.id)
        first_week = last_week - timedelta(weeks=weeks - 1)
        plans = await PlanService(self.session).plans_for_members(
            access.organization_id,
            [member.id for member in members],
            week_from=first_week,
            week_to=last_week,
        )
        history: list[WeekStats] = []
        for offset in range(weeks):
            week = last_week - timedelta(weeks=offset)
            week_plans = [plan for plan in plans if plan.week_start == week]
            history.append(summarize_week(week, len(members), week_plans))
        return history

    # --- Writes (organization owners and admins) ------------------------------------

    async def create_team(
        self,
        access: OrgAccess,
        *,
        name: str,
        description: str | None,
        lead_user_id: uuid.UUID | None,
        member_ids: Sequence[uuid.UUID],
    ) -> Team:
        await self._ensure_name_available(access.organization_id, name)
        # The lead is always a member of their team.
        wanted = list(member_ids)
        if lead_user_id is not None:
            wanted.append(lead_user_id)
        wanted = list(dict.fromkeys(wanted))
        await self._ensure_org_members(access.organization_id, wanted)

        team = Team(
            organization_id=access.organization_id,
            name=name,
            description=description or None,
            lead_user_id=lead_user_id,
        )
        self.session.add(team)
        await self.session.flush()
        self.session.add_all(
            TeamMembership(
                organization_id=access.organization_id, team_id=team.id, user_id=user_id
            )
            for user_id in wanted
        )
        await self.session.flush()
        return await self.get_team(access.organization_id, team.id)

    async def update_team(
        self, access: OrgAccess, team_id: uuid.UUID, changes: dict[str, Any]
    ) -> Team:
        """Partial update. `lead_user_id` may be set to null to clear the lead;
        a new lead who isn't on the team yet is added to it."""
        team = await self.get_team(access.organization_id, team_id)
        if "name" in changes and changes["name"] != team.name:
            await self._ensure_name_available(
                access.organization_id, changes["name"], exclude_id=team.id
            )
            team.name = changes["name"]
        if "description" in changes:
            team.description = changes["description"] or None
        if "lead_user_id" in changes:
            lead_id = changes["lead_user_id"]
            if lead_id is not None:
                await self._ensure_org_members(access.organization_id, [lead_id])
                await self._add_seat(access.organization_id, team.id, lead_id)
            team.lead_user_id = lead_id
        await self.session.flush()
        return await self.get_team(access.organization_id, team.id)

    async def delete_team(self, access: OrgAccess, team_id: uuid.UUID) -> None:
        team = await self.get_team(access.organization_id, team_id)
        await self.session.delete(team)
        await self.session.flush()

    async def add_member(
        self, access: OrgAccess, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> Team:
        team = await self.get_team(access.organization_id, team_id)
        await self._ensure_org_members(access.organization_id, [user_id])
        await self._add_seat(access.organization_id, team.id, user_id)
        await self.session.flush()
        return team

    async def remove_member(
        self, access: OrgAccess, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> Team:
        team = await self.get_team(access.organization_id, team_id)
        seat = await self.session.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team.id, TeamMembership.user_id == user_id
            )
        )
        if seat is None:
            raise ResourceNotFoundException("That person isn't on this team.")
        await self.session.delete(seat)
        if team.lead_user_id == user_id:
            team.lead_user_id = None
        await self.session.flush()
        return await self.get_team(access.organization_id, team.id)

    async def _add_seat(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        if not await self.is_member(team_id, user_id):
            self.session.add(
                TeamMembership(
                    organization_id=organization_id, team_id=team_id, user_id=user_id
                )
            )

    async def _ensure_org_members(
        self, organization_id: uuid.UUID, user_ids: Sequence[uuid.UUID]
    ) -> None:
        """Every id must belong to this organization. The composite foreign key
        would reject a stranger anyway; checking first gives a clear 400."""
        if not user_ids:
            return
        found = set(
            (
                await self.session.scalars(
                    select(Membership.user_id).where(
                        Membership.organization_id == organization_id,
                        Membership.user_id.in_(user_ids),
                    )
                )
            ).all()
        )
        if found != set(user_ids):
            raise ValidationException(
                "Teams can only include members of this organization.",
                field="member_ids",
            )

    async def _ensure_name_available(
        self,
        organization_id: uuid.UUID,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        stmt = select(Team.id).where(
            Team.organization_id == organization_id,
            func.lower(Team.name) == name.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(Team.id != exclude_id)
        if await self.session.scalar(stmt) is not None:
            raise ConflictException(
                f"There's already a team called {name}.", field="name"
            )
