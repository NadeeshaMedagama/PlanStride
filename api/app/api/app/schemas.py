from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import UUID4, EmailStr, Field, model_validator

from app.ai.schemas import FindingCategory
from app.domain import (
    MAX_GO_TO_MARKET_GOALS,
    MAX_SUB_GOALS,
    InvitableRole,
    InvitationStatus,
    OrgRole,
    PlanStatus,
    ReviewDecision,
    TaskKind,
    TaskStatus,
)
from app.schemas import DateTime, Model

# --- Auth & sign-up -------------------------------------------------------------------


class AuthRequest(Model):
    email: EmailStr
    password: str


class AuthResponse(Model):
    access_token: str


class SignupRequest(Model):
    """Email/password sign-up. A new user either starts an organization
    (`organization_name`) or joins one through an invite (`invite_token`)."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str | None = Field(default=None, min_length=2, max_length=120)
    invite_token: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _exactly_one_way_in(self) -> Self:
        if (self.organization_name is None) == (self.invite_token is None):
            raise ValueError(
                "Provide either an organization name or an invite token, not both."
            )
        return self


# --- Users ----------------------------------------------------------------------------


class UserResponse(Model):
    id: UUID4
    created_at: DateTime
    updated_at: DateTime | None
    first_name: str
    last_name: str
    email: str


class UserSummary(Model):
    id: UUID4
    first_name: str
    last_name: str
    email: str


# --- Organizations ---------------------------------------------------------------------


class OrganizationSummary(Model):
    id: UUID4
    name: str
    role: OrgRole
    is_suspended: bool


class OrganizationResponse(Model):
    id: UUID4
    name: str
    created_at: DateTime
    role: OrgRole
    member_count: int
    team_count: int


class OrganizationCreateRequest(Model):
    name: str = Field(min_length=2, max_length=120)


class OrganizationUpdateRequest(Model):
    name: str = Field(min_length=2, max_length=120)


class TeamRef(Model):
    id: UUID4
    name: str


class MemberResponse(Model):
    user: UserSummary
    role: OrgRole
    joined_at: DateTime
    teams: list[TeamRef]
    # False once platform staff deactivate the account: still a member (and
    # in the team history), but unable to sign in.
    is_active: bool


class MemberUpdateRequest(Model):
    role: OrgRole


# --- Invitations -----------------------------------------------------------------------


class InvitationResponse(Model):
    id: UUID4
    role: InvitableRole
    status: InvitationStatus
    created_at: DateTime
    expires_at: DateTime
    created_by: UserSummary | None
    accepted_by: UserSummary | None


class InvitationCreateRequest(Model):
    role: InvitableRole = "member"


class InvitationCreatedResponse(InvitationResponse):
    # Returned once, at creation. Only its hash is stored.
    token: str


class InvitationPreviewResponse(Model):
    organization_name: str
    role: InvitableRole
    invited_by: str | None
    expires_at: DateTime


# --- Teams -----------------------------------------------------------------------------


class TeamResponse(Model):
    id: UUID4
    name: str
    description: str | None
    lead: UserSummary | None
    member_count: int
    is_member: bool
    is_lead: bool


class TeamDetailResponse(TeamResponse):
    members: list[UserSummary]
    can_view_week: bool


class TeamCreateRequest(Model):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=280)
    lead_user_id: UUID4 | None = None
    member_ids: list[UUID4] = Field(default_factory=list, max_length=200)


class TeamUpdateRequest(Model):
    """Partial update; send `lead_user_id: null` to clear the lead."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=280)
    lead_user_id: UUID4 | None = None


# --- Plans -----------------------------------------------------------------------------


class PlanTaskInput(Model):
    """A sub-goal or go-to-market goal. Send an existing task's `id` to keep it
    (and its ticked state); omit it to add a new task."""

    id: UUID4 | None = None
    title: str = Field(min_length=1, max_length=200)


class PlanContentRequest(Model):
    main_task: str = Field(min_length=1, max_length=200)
    why_it_matters: str | None = Field(default=None, max_length=1000)
    sub_goals: list[PlanTaskInput] = Field(
        default_factory=list, max_length=MAX_SUB_GOALS
    )
    go_to_market: list[PlanTaskInput] = Field(
        default_factory=list, max_length=MAX_GO_TO_MARKET_GOALS
    )


class PlanCreateRequest(PlanContentRequest):
    week_start: date = Field(description="Monday of the week the plan is for.")


class PlanTaskResponse(Model):
    id: UUID4
    kind: TaskKind
    title: str
    status: TaskStatus
    position: int
    completed_at: DateTime | None


class PlanPermissionsResponse(Model):
    can_edit: bool
    can_delete: bool
    can_submit: bool
    can_withdraw: bool
    can_review: bool
    can_complete: bool
    can_tick: bool


class PlanResponse(Model):
    id: UUID4
    week_start: date
    status: PlanStatus
    author: UserSummary
    why_it_matters: str | None
    tasks: list[PlanTaskResponse]
    tasks_done: int
    tasks_total: int
    submitted_at: DateTime | None
    reviewed_at: DateTime | None
    reviewed_by: UserSummary | None
    review_decision: ReviewDecision | None
    review_comment: str | None
    completed_at: DateTime | None
    main_task_shipped: bool | None
    outcome_note: str | None
    created_at: DateTime
    updated_at: DateTime | None
    permissions: PlanPermissionsResponse


class PlanSummaryResponse(Model):
    """A plan in a list. `main_task` and task counts are null for drafts the
    viewer doesn't own: a draft is private until it's submitted."""

    id: UUID4
    week_start: date
    status: PlanStatus
    author: UserSummary
    main_task: str | None
    tasks_done: int | None
    tasks_total: int | None
    main_task_shipped: bool | None
    review_decision: ReviewDecision | None
    submitted_at: DateTime | None


class PlanListResponse(Model):
    items: list[PlanSummaryResponse]
    total: int
    limit: int
    offset: int


class MyWeekResponse(Model):
    week_start: date
    plan: PlanResponse | None
    # Who can approve this member's plan: leads of the teams they're on.
    reviewers: list[UserSummary]


class ReviewDecisionRequest(Model):
    comment: str | None = Field(default=None, max_length=1000)


class ReturnPlanRequest(Model):
    comment: str = Field(
        min_length=1,
        max_length=1000,
        description="What the member should change. Required when returning a plan.",
    )


class CompletePlanRequest(Model):
    main_task_shipped: bool
    outcome_note: str | None = Field(default=None, max_length=1000)


class TaskStatusRequest(Model):
    status: TaskStatus


class ReviewQueueItem(Model):
    plan: PlanSummaryResponse
    teams: list[TeamRef]


# --- Team week & history ----------------------------------------------------------------


class TeamWeekMember(Model):
    member: UserSummary
    is_lead: bool
    plan: PlanSummaryResponse | None


class TeamWeekStats(Model):
    members: int
    planned: int
    submitted: int
    approved: int
    done: int
    shipped: int
    tasks_done: int
    tasks_total: int


class TeamWeekResponse(Model):
    team: TeamRef
    lead: UserSummary | None
    week_start: date
    viewer_is_lead: bool
    stats: TeamWeekStats
    members: list[TeamWeekMember]


class TeamHistoryWeek(TeamWeekStats):
    week_start: date


class TeamHistoryResponse(Model):
    team: TeamRef
    weeks: list[TeamHistoryWeek]


# --- AI ----------------------------------------------------------------------------------


class ReviewTaskRequest(Model):
    key: str = Field(
        min_length=1,
        max_length=64,
        description="The editor's own id for this task; findings refer back to it.",
    )
    kind: TaskKind
    title: str = Field(min_length=1, max_length=200)


class PlanReviewRequest(Model):
    """The plan as it stands in the editor, saved or not."""

    week_start: date
    why_it_matters: str | None = Field(default=None, max_length=1000)
    tasks: list[ReviewTaskRequest] = Field(
        min_length=1, max_length=1 + MAX_SUB_GOALS + MAX_GO_TO_MARKET_GOALS
    )

    @model_validator(mode="after")
    def _one_main_task_and_unique_keys(self) -> Self:
        if sum(task.kind == "main" for task in self.tasks) != 1:
            raise ValueError("A plan has exactly one main task.")
        if len({task.key for task in self.tasks}) != len(self.tasks):
            raise ValueError("Task keys must be unique.")
        return self


class ReviewFindingResponse(Model):
    task_key: str | None = Field(
        description="Editor key of the task this is about; null for plan-level."
    )
    category: FindingCategory
    problem: str
    suggested_rewrite: str
    action: Literal["replace_title", "set_why", "add_go_to_market"] = Field(
        description=(
            "What applying the suggestion does: replace the task's title, set the "
            "main task's why-it-matters, or add a go-to-market goal."
        )
    )


class PlanReviewResponse(Model):
    verdict: Literal["ready", "needs_work"]
    summary: str
    findings: list[ReviewFindingResponse]


class PlanDraftRequest(Model):
    week_start: date
    notes: str = Field(min_length=10, max_length=4000)


class PlanDraftResponse(Model):
    """A suggested plan for the editor. It is never saved by this call."""

    main_task: str
    why_it_matters: str
    sub_goals: list[str]
    go_to_market: list[str]
    left_out: list[str]
    open_questions: list[str]
