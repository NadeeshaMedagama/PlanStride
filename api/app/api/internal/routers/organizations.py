import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Query

from app.api.internal.access import CurrentInternalUser
from app.api.internal.schemas import (
    AIUsageTotals,
    InternalOrganizationDetailResponse,
    InternalOrganizationResponse,
    OrganizationMemberResponse,
    OrganizationsListResponse,
    OrganizationTeamResponse,
    PlanStatusCounts,
    SuspendOrganizationRequest,
    UserRef,
)
from app.database import DBSession
from app.domain import utcnow
from app.models import User
from app.services.ai_usage import AIUsageService
from app.services.backoffice import BackofficeService, OrganizationStats

router = APIRouter()


def _user_ref(user: User) -> UserRef:
    return UserRef(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )


def _organization_response(stats: OrganizationStats) -> InternalOrganizationResponse:
    organization = stats.organization
    return InternalOrganizationResponse(
        id=organization.id,
        name=organization.name,
        created_at=organization.created_at,
        suspended_at=organization.suspended_at,
        suspension_reason=organization.suspension_reason,
        member_count=stats.member_count,
        team_count=stats.team_count,
        plan_count=stats.plan_count,
        last_active_at=stats.last_active_at,
        owners=[_user_ref(owner) for owner in stats.owners],
    )


async def _detail(
    session: DBSession, organization_id: uuid.UUID
) -> InternalOrganizationDetailResponse:
    detail = await BackofficeService(session).get_organization(organization_id)
    usage = await AIUsageService(session).totals(
        since=utcnow() - timedelta(days=30), organization_id=organization_id
    )
    return InternalOrganizationDetailResponse(
        **_organization_response(detail.stats).model_dump(),
        members=[
            OrganizationMemberResponse(
                user=_user_ref(row.user),
                role=row.role,
                is_active=row.user.is_active,
                joined_at=row.joined_at,
            )
            for row in detail.members
        ],
        teams=[
            OrganizationTeamResponse(
                id=team.id,
                name=team.name,
                member_count=team.member_count,
                lead=_user_ref(team.lead) if team.lead else None,
            )
            for team in detail.teams
        ],
        plans_by_status=PlanStatusCounts(
            draft=detail.plans_by_status.get("draft", 0),
            submitted=detail.plans_by_status.get("submitted", 0),
            approved=detail.plans_by_status.get("approved", 0),
            done=detail.plans_by_status.get("done", 0),
        ),
        ai_usage_30d=AIUsageTotals.model_validate(usage),
    )


@router.get("/organizations", tags=["organizations"])
async def organization_list(
    current_user: CurrentInternalUser,
    session: DBSession,
    search: str | None = Query(None, max_length=100),
    status: Literal["active", "suspended"] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> OrganizationsListResponse:
    """Every customer organization with its size and when it was last active,
    most recently active first."""
    items, total = await BackofficeService(session).list_organizations(
        search=search, status=status, limit=limit, offset=offset
    )
    return OrganizationsListResponse(
        items=[_organization_response(stats) for stats in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/organizations/{organization_id}", tags=["organizations"])
async def organization_get(
    current_user: CurrentInternalUser, session: DBSession, organization_id: uuid.UUID
) -> InternalOrganizationDetailResponse:
    """Members, teams, plan counts by status and AI usage. Plan content is
    deliberately not available to staff."""
    return await _detail(session, organization_id)


@router.post("/organizations/{organization_id}/suspend", tags=["organizations"])
async def organization_suspend(
    current_user: CurrentInternalUser,
    session: DBSession,
    organization_id: uuid.UUID,
    data: SuspendOrganizationRequest,
) -> InternalOrganizationDetailResponse:
    """Lock every member out of the organization until it's reinstated."""
    await BackofficeService(session).suspend(organization_id, data.reason)
    await session.commit()
    return await _detail(session, organization_id)


@router.post("/organizations/{organization_id}/reinstate", tags=["organizations"])
async def organization_reinstate(
    current_user: CurrentInternalUser, session: DBSession, organization_id: uuid.UUID
) -> InternalOrganizationDetailResponse:
    await BackofficeService(session).reinstate(organization_id)
    await session.commit()
    return await _detail(session, organization_id)
