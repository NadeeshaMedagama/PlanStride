"""Internal (staff) API shapes.

None of these carry customer content: no plan or task text, review comments,
outcome notes or AI prompts. Staff need to know who belongs where and how the
product is used, not what customers wrote.
"""

from __future__ import annotations

from datetime import date

from pydantic import UUID4, EmailStr, Field

from app.domain import AIErrorType, AIFeature, AIOutcome, OrgRole
from app.schemas import DateTime, Model


class AuthRequest(Model):
    email: EmailStr
    password: str


class AuthResponse(Model):
    access_token: str


# --- Users ----------------------------------------------------------------------------


class UserMembershipResponse(Model):
    organization_id: UUID4
    organization_name: str
    role: OrgRole
    is_suspended: bool


class InternalUserResponse(Model):
    id: UUID4
    created_at: DateTime
    updated_at: DateTime | None
    first_name: str
    last_name: str
    email: str
    is_platform_staff: bool
    is_active: bool
    last_login_at: DateTime | None
    memberships: list[UserMembershipResponse]


class UsersListResponse(Model):
    items: list[InternalUserResponse]
    total: int
    limit: int
    offset: int


class UserUpdateRequest(Model):
    """Staff access is deliberately not editable here; it is granted with
    `manage.py create-user --admin`."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    is_active: bool | None = None


class UserChangePasswordRequest(Model):
    password: str = Field(min_length=8, max_length=128)


# --- Organizations --------------------------------------------------------------------


class UserRef(Model):
    id: UUID4
    first_name: str
    last_name: str
    email: str


class InternalOrganizationResponse(Model):
    id: UUID4
    name: str
    created_at: DateTime
    suspended_at: DateTime | None
    suspension_reason: str | None
    member_count: int
    team_count: int
    plan_count: int
    last_active_at: DateTime
    owners: list[UserRef]


class OrganizationsListResponse(Model):
    items: list[InternalOrganizationResponse]
    total: int
    limit: int
    offset: int


class OrganizationMemberResponse(Model):
    user: UserRef
    role: OrgRole
    is_active: bool
    joined_at: DateTime


class OrganizationTeamResponse(Model):
    id: UUID4
    name: str
    member_count: int
    lead: UserRef | None


class PlanStatusCounts(Model):
    draft: int
    submitted: int
    approved: int
    done: int


class AIUsageTotals(Model):
    calls: int
    succeeded: int
    failed: int
    rate_limited: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: int | None


class InternalOrganizationDetailResponse(InternalOrganizationResponse):
    members: list[OrganizationMemberResponse]
    teams: list[OrganizationTeamResponse]
    plans_by_status: PlanStatusCounts
    ai_usage_30d: AIUsageTotals


class SuspendOrganizationRequest(Model):
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Internal note on why; not shown to the customer.",
    )


# --- AI usage --------------------------------------------------------------------------


class AIUsageByOrganization(Model):
    organization_id: UUID4
    organization_name: str
    last_call_at: DateTime | None
    totals: AIUsageTotals


class AIUsageByFeature(Model):
    feature: AIFeature
    totals: AIUsageTotals


class AIUsageDay(Model):
    day: date
    succeeded: int
    failed: int
    rate_limited: int


class AIUsageErrorCount(Model):
    error_type: AIErrorType
    count: int


class AIUsageSummaryResponse(Model):
    days: int
    model_name: str
    totals: AIUsageTotals
    by_organization: list[AIUsageByOrganization]
    by_feature: list[AIUsageByFeature]
    by_day: list[AIUsageDay]
    by_error_type: list[AIUsageErrorCount]


class AIUsageEventResponse(Model):
    id: UUID4
    created_at: DateTime
    organization_id: UUID4
    organization_name: str
    user_email: str | None
    feature: AIFeature
    outcome: AIOutcome
    error_type: AIErrorType | None
    model_name: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None


class AIUsageEventsResponse(Model):
    items: list[AIUsageEventResponse]
    total: int
    limit: int
    offset: int


# --- Overview ----------------------------------------------------------------------------


class OverviewResponse(Model):
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
