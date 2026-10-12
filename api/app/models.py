from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
    types,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain import (
    AI_ERROR_TYPES,
    AI_FEATURES,
    AI_OUTCOMES,
    INVITABLE_ROLES,
    ORG_ROLES,
    PLAN_STATUSES,
    REVIEW_DECISIONS,
    TASK_KINDS,
    TASK_STATUSES,
    AIErrorType,
    AIFeature,
    AIOutcome,
    InvitableRole,
    OrgRole,
    PlanStatus,
    ReviewDecision,
    TaskKind,
    TaskStatus,
    sql_in,
    utcnow,
)


class IdMixin:
    # Mixin columns sort after the model's own columns by default; keep the
    # primary key first in generated migrations.
    id: Mapped[uuid.UUID] = mapped_column(
        types.Uuid, primary_key=True, default=uuid.uuid4, sort_order=-1
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=utcnow, nullable=True
    )


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # PlanStride's own back-office staff: the only users who can sign in to the
    # internal console. This is NOT a customer role. An organization's "admin"
    # is `Membership.role`. The column keeps the template's `is_admin` name; the
    # attribute is named for what it means so the two can't be mixed up in code.
    is_platform_staff: Mapped[bool] = mapped_column(
        "is_admin", Boolean, nullable=False, default=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Organization(IdMixin, TimestampMixin, Base):
    """A customer: the tenancy boundary. Every customer record hangs off one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Set by platform staff. While set, members are locked out of the
    # organization (enforced by the app API's organization access check).
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspension_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None


class Membership(IdMixin, TimestampMixin, Base):
    """A user's place in an organization, with their customer role."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", name="uq_memberships_organization_user"
        ),
        CheckConstraint(sql_in("role", ORG_ROLES), name="ck_memberships_role"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[OrgRole] = mapped_column(String(20), nullable=False)

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()


class Invitation(IdMixin, TimestampMixin, Base):
    """A single-use, expiring invite link into an organization."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(sql_in("role", INVITABLE_ROLES), name="ck_invitations_role"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[InvitableRole] = mapped_column(String(20), nullable=False)
    # SHA-256 of the token. The token itself only exists in the link handed to
    # the inviter once, so a database leak doesn't hand out working invites.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    accepted_by: Mapped[User | None] = relationship(foreign_keys=[accepted_by_id])


class Team(IdMixin, TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_teams_organization_name"),
        # Referenced by team_memberships' composite foreign key, so a team
        # membership can only ever point at a team in its own organization.
        UniqueConstraint("organization_id", "id", name="uq_teams_organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(280), nullable=True)
    # The lead approves the plans of the team's members. Services keep the lead
    # a member of the team; approval checks require both, so a stale lead
    # (e.g. someone removed from the team) never keeps approval rights.
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lead: Mapped[User | None] = relationship()


class TeamMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_memberships_team_user"),
        # Both keys carry organization_id, so Postgres itself refuses to pair a
        # team with a user from another organization, and removing someone from
        # the organization removes them from all of its teams.
        ForeignKeyConstraint(
            ["organization_id", "team_id"],
            ["teams.organization_id", "teams.id"],
            name="fk_team_memberships_team",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_team_memberships_membership",
            ondelete="CASCADE",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        types.Uuid, nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(types.Uuid, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(types.Uuid, nullable=False, index=True)


class WeeklyPlan(IdMixin, TimestampMixin, Base):
    """One member's plan for one week, keyed by that week's Monday."""

    __tablename__ = "weekly_plans"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "week_start",
            name="uq_weekly_plans_member_week",
        ),
        CheckConstraint(
            "extract(isodow from week_start) = 1",
            name="ck_weekly_plans_week_start_monday",
        ),
        CheckConstraint(sql_in("status", PLAN_STATUSES), name="ck_weekly_plans_status"),
        CheckConstraint(
            f"review_decision IS NULL OR {sql_in('review_decision', REVIEW_DECISIONS)}",
            name="ck_weekly_plans_review_decision",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Plain user FK rather than a membership FK: a plan stays in the team's
    # history even if its author later leaves the organization.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    # Lives on the plan rather than the task: a plan has exactly one main task.
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_decision: Mapped[ReviewDecision | None] = mapped_column(
        String(20), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    main_task_shipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    author: Mapped[User] = relationship(foreign_keys=[user_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    # Positions run across the whole plan: main task first, then sub-goals,
    # then go-to-market goals, in the order the member wrote them.
    tasks: Mapped[list[PlanTask]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanTask.position",
    )


class PlanTask(IdMixin, TimestampMixin, Base):
    """One checkable item in a plan: the main task, a sub-goal or a GTM goal."""

    __tablename__ = "plan_tasks"
    __table_args__ = (
        CheckConstraint(sql_in("kind", TASK_KINDS), name="ck_plan_tasks_kind"),
        CheckConstraint(sql_in("status", TASK_STATUSES), name="ck_plan_tasks_status"),
        # One significant thing per week: at most one main task per plan, as a
        # database guarantee rather than a convention.
        Index(
            "uq_plan_tasks_one_main_per_plan",
            "plan_id",
            unique=True,
            postgresql_where=text("kind = 'main'"),
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[TaskKind] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        String(10), nullable=False, default="todo"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    plan: Mapped[WeeklyPlan] = relationship(back_populates="tasks")


class AIUsageEvent(IdMixin, Base):
    """One call to the AI, recorded against the organization that made it.

    Deliberately content-free: no prompt, plan text or model output is stored,
    so the usage view in the internal console can't leak customer plans.
    """

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        CheckConstraint(sql_in("feature", AI_FEATURES), name="ck_ai_usage_feature"),
        CheckConstraint(sql_in("outcome", AI_OUTCOMES), name="ck_ai_usage_outcome"),
        CheckConstraint(
            f"error_type IS NULL OR {sql_in('error_type', AI_ERROR_TYPES)}",
            name="ck_ai_usage_error_type",
        ),
        Index("ix_ai_usage_events_org_created", "organization_id", "created_at"),
        Index("ix_ai_usage_events_user_created", "user_id", "created_at"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feature: Mapped[AIFeature] = mapped_column(String(30), nullable=False)
    outcome: Mapped[AIOutcome] = mapped_column(String(20), nullable=False)
    error_type: Mapped[AIErrorType | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
