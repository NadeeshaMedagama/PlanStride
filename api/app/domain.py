"""Domain vocabulary shared by models, services, schemas and the AI agents.

Status-like columns are plain strings (AGENTS.md: no enums in models). The
allowed values live here once, as `Literal` types for the API schemas and as
tuples for the CHECK constraints in `app.models`, so the API and the database
can't drift apart.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal, get_args

# --- Organization roles -------------------------------------------------------
# Customer-side roles inside one organization. These have nothing to do with
# `User.is_platform_staff`, which is PlanStride's own back-office flag.
OrgRole = Literal["owner", "admin", "member"]
ORG_ROLES: tuple[OrgRole, ...] = get_args(OrgRole)
ORG_ROLE_OWNER: OrgRole = "owner"
ORG_ROLE_ADMIN: OrgRole = "admin"
ORG_ROLE_MEMBER: OrgRole = "member"
# Owners and admins manage members, teams and settings.
ORG_MANAGER_ROLES: frozenset[str] = frozenset({ORG_ROLE_OWNER, ORG_ROLE_ADMIN})

# An invite can't hand out ownership; owners are made by promotion only.
InvitableRole = Literal["admin", "member"]
INVITABLE_ROLES: tuple[InvitableRole, ...] = get_args(InvitableRole)
INVITATION_TTL = timedelta(days=7)
InvitationStatus = Literal["pending", "accepted", "revoked", "expired"]

# --- Weekly plans -------------------------------------------------------------
# draft -> submitted -> approved -> done. A lead returning a plan sends it back
# to draft with their comment kept on the plan.
PlanStatus = Literal["draft", "submitted", "approved", "done"]
PLAN_STATUSES: tuple[PlanStatus, ...] = get_args(PlanStatus)

ReviewDecision = Literal["approved", "returned"]
REVIEW_DECISIONS: tuple[ReviewDecision, ...] = get_args(ReviewDecision)

TaskKind = Literal["main", "sub_goal", "go_to_market"]
TASK_KINDS: tuple[TaskKind, ...] = get_args(TaskKind)

TaskStatus = Literal["todo", "done"]
TASK_STATUSES: tuple[TaskStatus, ...] = get_args(TaskStatus)

MAX_SUB_GOALS = 8
MAX_GO_TO_MARKET_GOALS = 6

# How far from the current week a member may open a new plan: last week (to
# catch up on a Monday) through four weeks ahead.
PLANNING_WINDOW_PAST = timedelta(weeks=1)
PLANNING_WINDOW_FUTURE = timedelta(weeks=4)

# --- AI usage -----------------------------------------------------------------
AIFeature = Literal["plan_review", "plan_draft"]
AI_FEATURES: tuple[AIFeature, ...] = get_args(AIFeature)

# `rate_limited` is split out from `failed` because it is the failure the free
# Gemini tier produces most, and the one staff act on differently.
AIOutcome = Literal["success", "failed", "rate_limited"]
AI_OUTCOMES: tuple[AIOutcome, ...] = get_args(AIOutcome)

AIErrorType = Literal[
    "provider_rate_limit",  # Gemini answered 429
    "throttled",  # our own per-user limit, the provider was never called
    "timeout",
    "provider_error",  # Gemini unreachable or answered an error status
    "invalid_output",  # the model kept returning output that failed validation
    "not_configured",  # no GOOGLE_API_KEY on the server
    "internal_error",
]
AI_ERROR_TYPES: tuple[AIErrorType, ...] = get_args(AIErrorType)


def utcnow() -> datetime:
    return datetime.now(UTC)


def week_start_of(day: date) -> date:
    """The Monday of the week `day` falls in. Plans are keyed by this date."""
    return day - timedelta(days=day.weekday())


def current_week_start() -> date:
    return week_start_of(utcnow().date())


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Render a CHECK constraint body that pins a string column to `values`."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
