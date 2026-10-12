import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.domain import (
    PLANNING_WINDOW_FUTURE,
    PLANNING_WINDOW_PAST,
    PlanStatus,
    ReviewDecision,
    TaskKind,
    TaskStatus,
    current_week_start,
    utcnow,
)
from app.exceptions import (
    ConflictException,
    ForbiddenException,
    InvalidStateException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models import PlanTask, Team, TeamMembership, User, WeeklyPlan
from app.tenancy import OrgAccess

# Tasks can be ticked off while the week is live; a closed week is history.
TICKABLE_STATUSES: frozenset[str] = frozenset({"draft", "submitted", "approved"})


@dataclass(frozen=True)
class TaskDraft:
    """A sub-goal or go-to-market goal as the member wrote it. `id` refers to an
    existing task (keeping its ticked state); None creates a new one."""

    id: uuid.UUID | None
    title: str


@dataclass(frozen=True)
class PlanContent:
    main_task: str
    why_it_matters: str | None
    sub_goals: Sequence[TaskDraft]
    go_to_market: Sequence[TaskDraft]


@dataclass(frozen=True)
class PlanPermissions:
    """What the current viewer may do with a plan. Sent to the UI so it never
    shows a button the API would refuse; the API still checks every action."""

    can_edit: bool
    can_delete: bool
    can_submit: bool
    can_withdraw: bool
    can_review: bool
    can_complete: bool
    can_tick: bool


class PlanService:
    """Weekly plans: content, lifecycle, visibility and who may review them.

    Visibility: a draft is private to its author. Once submitted, a plan is
    visible to the author's teammates (which includes their leads) and to the
    organization's owners and admins. Anyone else gets a 404.

    Review: a plan is approved or returned by the lead of a team that both the
    lead and the author belong to, never by the author. Organization owners and
    admins get no approval rights from their role alone.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Reads -----------------------------------------------------------------

    def plans_query(self, organization_id: uuid.UUID) -> Select[tuple[WeeklyPlan]]:
        """Plans of one organization, with what a response needs preloaded."""
        return (
            select(WeeklyPlan)
            .where(WeeklyPlan.organization_id == organization_id)
            .options(
                selectinload(WeeklyPlan.tasks),
                selectinload(WeeklyPlan.author),
                selectinload(WeeklyPlan.reviewed_by),
            )
        )

    async def get_plan(
        self, organization_id: uuid.UUID, plan_id: uuid.UUID
    ) -> WeeklyPlan:
        plan = await self.session.scalar(
            self.plans_query(organization_id)
            .where(WeeklyPlan.id == plan_id)
            # Re-read after a write so relationships reflect the flushed state.
            .execution_options(populate_existing=True)
        )
        if plan is None:
            raise ResourceNotFoundException("Plan not found")
        return plan

    async def get_visible_plan(
        self, access: OrgAccess, plan_id: uuid.UUID
    ) -> WeeklyPlan:
        plan = await self.get_plan(access.organization_id, plan_id)
        if not await self.can_view(access, plan):
            raise ResourceNotFoundException("Plan not found")
        return plan

    async def get_own_plan(self, access: OrgAccess, plan_id: uuid.UUID) -> WeeklyPlan:
        plan = await self.get_visible_plan(access, plan_id)
        if plan.user_id != access.user_id:
            raise ForbiddenException("Only the plan's author can do this.")
        return plan

    async def plan_for_week(
        self, access: OrgAccess, week_start: date
    ) -> WeeklyPlan | None:
        return await self.session.scalar(
            self.plans_query(access.organization_id).where(
                WeeklyPlan.user_id == access.user_id,
                WeeklyPlan.week_start == week_start,
            )
        )

    async def list_own_plans(
        self, access: OrgAccess, *, limit: int, offset: int
    ) -> tuple[Sequence[WeeklyPlan], int]:
        conditions = (
            WeeklyPlan.organization_id == access.organization_id,
            WeeklyPlan.user_id == access.user_id,
        )
        total = await self.session.scalar(
            select(func.count()).select_from(WeeklyPlan).where(*conditions)
        )
        result = await self.session.execute(
            self.plans_query(access.organization_id)
            .where(*conditions)
            .order_by(WeeklyPlan.week_start.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total or 0

    async def plans_for_members(
        self,
        organization_id: uuid.UUID,
        user_ids: Sequence[uuid.UUID],
        *,
        week_from: date,
        week_to: date,
    ) -> Sequence[WeeklyPlan]:
        if not user_ids:
            return []
        result = await self.session.execute(
            self.plans_query(organization_id).where(
                WeeklyPlan.user_id.in_(user_ids),
                WeeklyPlan.week_start >= week_from,
                WeeklyPlan.week_start <= week_to,
            )
        )
        return result.scalars().all()

    async def review_queue(self, access: OrgAccess) -> Sequence[WeeklyPlan]:
        """Submitted plans the caller can review, oldest submission first."""
        lead_seat = aliased(TeamMembership)
        author_seat = aliased(TeamMembership)
        led_teams = (
            select(Team.id)
            .join(
                lead_seat,
                and_(
                    lead_seat.team_id == Team.id,
                    lead_seat.user_id == Team.lead_user_id,
                ),
            )
            .where(
                Team.organization_id == access.organization_id,
                Team.lead_user_id == access.user_id,
            )
        )
        authors = select(author_seat.user_id).where(
            author_seat.team_id.in_(led_teams),
            author_seat.user_id != access.user_id,
        )
        result = await self.session.execute(
            self.plans_query(access.organization_id)
            .where(WeeklyPlan.status == "submitted", WeeklyPlan.user_id.in_(authors))
            .order_by(WeeklyPlan.submitted_at)
        )
        return result.scalars().all()

    async def led_teams_by_author(
        self, access: OrgAccess, author_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[Team]]:
        """For each author, the teams they share with the caller as its lead."""
        if not author_ids:
            return {}
        author_seat = aliased(TeamMembership)
        rows = await self.session.execute(
            select(author_seat.user_id, Team)
            .join(Team, Team.id == author_seat.team_id)
            .where(
                Team.organization_id == access.organization_id,
                Team.lead_user_id == access.user_id,
                author_seat.user_id.in_(author_ids),
            )
            .order_by(Team.name)
        )
        teams: dict[uuid.UUID, list[Team]] = {}
        for author_id, team in rows.tuples():
            teams.setdefault(author_id, []).append(team)
        return teams

    # --- Visibility and review rights ---------------------------------------------

    async def can_view(self, access: OrgAccess, plan: WeeklyPlan) -> bool:
        if plan.user_id == access.user_id:
            return True
        if plan.status == "draft":
            return False
        if access.can_manage:
            return True
        return await self.shares_team(
            access.organization_id, access.user_id, plan.user_id
        )

    async def shares_team(
        self, organization_id: uuid.UUID, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> bool:
        seat_a = aliased(TeamMembership)
        seat_b = aliased(TeamMembership)
        stmt = select(
            select(seat_a.id)
            .join(seat_b, seat_b.team_id == seat_a.team_id)
            .where(
                seat_a.organization_id == organization_id,
                seat_a.user_id == user_a,
                seat_b.user_id == user_b,
            )
            .exists()
        )
        return bool(await self.session.scalar(stmt))

    def _reviewer_ids(
        self, organization_id: uuid.UUID, author_id: uuid.UUID
    ) -> Select[tuple[uuid.UUID | None]]:
        """Leads of the teams the author is on. The lead must also still be a
        member of that team, and never the author themselves."""
        author_seat = aliased(TeamMembership)
        lead_seat = aliased(TeamMembership)
        return (
            select(Team.lead_user_id)
            .join(
                author_seat,
                and_(author_seat.team_id == Team.id, author_seat.user_id == author_id),
            )
            .join(
                lead_seat,
                and_(
                    lead_seat.team_id == Team.id,
                    lead_seat.user_id == Team.lead_user_id,
                ),
            )
            .where(
                Team.organization_id == organization_id,
                Team.lead_user_id != author_id,
            )
        )

    async def reviewers_for(
        self, organization_id: uuid.UUID, author_id: uuid.UUID
    ) -> Sequence[User]:
        result = await self.session.execute(
            select(User)
            .where(User.id.in_(self._reviewer_ids(organization_id, author_id)))
            .order_by(User.first_name, User.last_name)
        )
        return result.scalars().all()

    async def can_review(
        self, organization_id: uuid.UUID, reviewer_id: uuid.UUID, author_id: uuid.UUID
    ) -> bool:
        if reviewer_id == author_id:
            return False
        stmt = select(
            self._reviewer_ids(organization_id, author_id)
            .where(Team.lead_user_id == reviewer_id)
            .exists()
        )
        return bool(await self.session.scalar(stmt))

    async def permissions(self, access: OrgAccess, plan: WeeklyPlan) -> PlanPermissions:
        is_author = plan.user_id == access.user_id
        status = plan.status
        can_review = (
            not is_author
            and status == "submitted"
            and await self.can_review(
                access.organization_id, access.user_id, plan.user_id
            )
        )
        return PlanPermissions(
            can_edit=is_author and status == "draft",
            can_delete=is_author and status == "draft",
            can_submit=is_author and status == "draft",
            can_withdraw=is_author and status == "submitted",
            can_review=can_review,
            can_complete=is_author and status == "approved",
            can_tick=is_author and status in TICKABLE_STATUSES,
        )

    # --- Writes ------------------------------------------------------------------

    async def create_plan(
        self, access: OrgAccess, week_start: date, content: PlanContent
    ) -> WeeklyPlan:
        _validate_planning_week(week_start)
        existing = await self.session.scalar(
            select(WeeklyPlan.id).where(
                WeeklyPlan.organization_id == access.organization_id,
                WeeklyPlan.user_id == access.user_id,
                WeeklyPlan.week_start == week_start,
            )
        )
        if existing is not None:
            raise _duplicate_week()

        plan = WeeklyPlan(
            organization_id=access.organization_id,
            author=access.user,
            week_start=week_start,
            status="draft",
            tasks=[PlanTask(kind="main", title=content.main_task, position=0)],
        )
        _apply_content(plan, content)
        self.session.add(plan)
        try:
            await self.session.flush()
        except IntegrityError as e:
            # Lost a race with a concurrent create for the same week.
            raise _duplicate_week() from e
        return await self.get_plan(access.organization_id, plan.id)

    async def update_plan(
        self, access: OrgAccess, plan_id: uuid.UUID, content: PlanContent
    ) -> WeeklyPlan:
        plan = await self.get_own_plan(access, plan_id)
        _require_status(plan, "draft", "Only a draft can be edited.")
        _apply_content(plan, content)
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def delete_plan(self, access: OrgAccess, plan_id: uuid.UUID) -> None:
        plan = await self.get_own_plan(access, plan_id)
        _require_status(plan, "draft", "Only a draft can be deleted.")
        await self.session.delete(plan)
        await self.session.flush()

    async def submit(self, access: OrgAccess, plan_id: uuid.UUID) -> WeeklyPlan:
        plan = await self.get_own_plan(access, plan_id)
        _require_status(plan, "draft", "Only a draft can be submitted.")
        plan.status = "submitted"
        plan.submitted_at = utcnow()
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def withdraw(self, access: OrgAccess, plan_id: uuid.UUID) -> WeeklyPlan:
        plan = await self.get_own_plan(access, plan_id)
        _require_status(
            plan, "submitted", "Only a plan awaiting review can be withdrawn."
        )
        plan.status = "draft"
        plan.submitted_at = None
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def approve(
        self, access: OrgAccess, plan_id: uuid.UUID, comment: str | None
    ) -> WeeklyPlan:
        plan = await self.get_visible_plan(access, plan_id)
        await self._require_reviewer(access, plan)
        _require_status(plan, "submitted", "Only a submitted plan can be approved.")
        plan.status = "approved"
        self._record_review(plan, access.user, "approved", comment)
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def return_to_author(
        self, access: OrgAccess, plan_id: uuid.UUID, comment: str
    ) -> WeeklyPlan:
        """Send a submitted plan back to draft with the lead's comment, which
        stays on the plan while the author revises it."""
        plan = await self.get_visible_plan(access, plan_id)
        await self._require_reviewer(access, plan)
        _require_status(plan, "submitted", "Only a submitted plan can be returned.")
        plan.status = "draft"
        plan.submitted_at = None
        self._record_review(plan, access.user, "returned", comment)
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def complete(
        self,
        access: OrgAccess,
        plan_id: uuid.UUID,
        *,
        main_task_shipped: bool,
        outcome_note: str | None,
    ) -> WeeklyPlan:
        """Close the week: record whether the main task shipped."""
        plan = await self.get_own_plan(access, plan_id)
        _require_status(plan, "approved", "Only an approved plan can be closed out.")
        now = utcnow()
        plan.status = "done"
        plan.completed_at = now
        plan.main_task_shipped = main_task_shipped
        plan.outcome_note = outcome_note or None
        if main_task_shipped:
            for task in plan.tasks:
                if task.kind == "main" and task.status != "done":
                    task.status = "done"
                    task.completed_at = now
        await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def set_task_status(
        self,
        access: OrgAccess,
        plan_id: uuid.UUID,
        task_id: uuid.UUID,
        status: TaskStatus,
    ) -> WeeklyPlan:
        plan = await self.get_own_plan(access, plan_id)
        if plan.status not in TICKABLE_STATUSES:
            raise InvalidStateException(
                "This week is closed, so its tasks can't change."
            )
        task = next((t for t in plan.tasks if t.id == task_id), None)
        if task is None:
            raise ResourceNotFoundException("Task not found")
        if task.status != status:
            task.status = status
            task.completed_at = utcnow() if status == "done" else None
            await self.session.flush()
        return await self.get_plan(access.organization_id, plan.id)

    async def _require_reviewer(self, access: OrgAccess, plan: WeeklyPlan) -> None:
        if plan.user_id == access.user_id:
            raise ForbiddenException(
                "You can't review your own plan.", code="SELF_REVIEW"
            )
        if not await self.can_review(
            access.organization_id, access.user_id, plan.user_id
        ):
            raise ForbiddenException(
                "Only the lead of one of this member's teams can review their plan.",
                code="TEAM_LEAD_REQUIRED",
            )

    @staticmethod
    def _record_review(
        plan: WeeklyPlan,
        reviewer: User,
        decision: ReviewDecision,
        comment: str | None,
    ) -> None:
        plan.reviewed_by = reviewer
        plan.reviewed_at = utcnow()
        plan.review_decision = decision
        plan.review_comment = comment or None


def _apply_content(plan: WeeklyPlan, content: PlanContent) -> None:
    """Replace the plan's content. Existing tasks referenced by id keep their
    status; tasks no longer listed are deleted (delete-orphan)."""
    main = next(task for task in plan.tasks if task.kind == "main")
    main.title = content.main_task
    main.position = 0
    plan.why_it_matters = content.why_it_matters or None

    existing = {task.id: task for task in plan.tasks if task.kind != "main"}
    kept: list[PlanTask] = [main]
    seen: set[uuid.UUID] = set()
    groups: tuple[tuple[TaskKind, Sequence[TaskDraft]], ...] = (
        ("sub_goal", content.sub_goals),
        ("go_to_market", content.go_to_market),
    )
    for kind, drafts in groups:
        for draft in drafts:
            position = len(kept)
            if draft.id is None:
                kept.append(PlanTask(kind=kind, title=draft.title, position=position))
                continue
            task = existing.get(draft.id)
            if task is None or task.kind != kind or draft.id in seen:
                raise ValidationException(
                    "A task in this request doesn't belong to this plan.",
                    field=kind,
                )
            seen.add(draft.id)
            task.title = draft.title
            task.position = position
            kept.append(task)
    plan.tasks = kept


def _validate_planning_week(week_start: date) -> None:
    if week_start.weekday() != 0:
        raise ValidationException(
            "Plans are keyed by the Monday of their week.", field="week_start"
        )
    current = current_week_start()
    if (
        not current - PLANNING_WINDOW_PAST
        <= week_start
        <= current + PLANNING_WINDOW_FUTURE
    ):
        raise ValidationException(
            "You can plan from last week up to four weeks ahead.", field="week_start"
        )


def _require_status(plan: WeeklyPlan, status: PlanStatus, message: str) -> None:
    if plan.status != status:
        raise InvalidStateException(message)


def _duplicate_week() -> ConflictException:
    return ConflictException(
        "You already have a plan for this week.", field="week_start"
    )
