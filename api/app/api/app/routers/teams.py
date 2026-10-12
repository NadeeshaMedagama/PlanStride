import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.app.access import OrgManager, OrgMember
from app.api.app.presenters import plan_summary, user_summary
from app.api.app.schemas import (
    TeamCreateRequest,
    TeamDetailResponse,
    TeamHistoryResponse,
    TeamHistoryWeek,
    TeamRef,
    TeamResponse,
    TeamUpdateRequest,
    TeamWeekMember,
    TeamWeekResponse,
    TeamWeekStats,
)
from app.database import DBSession
from app.domain import current_week_start, week_start_of
from app.exceptions import ValidationException
from app.models import Team
from app.services.teams import TeamService, WeekStats, summarize_week
from app.tenancy import OrgAccess

router = APIRouter()


async def _team_detail(
    service: TeamService, access: OrgAccess, team: Team
) -> TeamDetailResponse:
    members = await service.list_members(team.id)
    member_ids = {member.id for member in members}
    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        lead=user_summary(team.lead) if team.lead else None,
        member_count=len(members),
        is_member=access.user_id in member_ids,
        is_lead=team.lead_user_id == access.user_id,
        members=[user_summary(member) for member in members],
        can_view_week=await service.can_view_week(access, team),
    )


def _stats(stats: WeekStats) -> TeamWeekStats:
    return TeamWeekStats(
        members=stats.members,
        planned=stats.planned,
        submitted=stats.submitted,
        approved=stats.approved,
        done=stats.done,
        shipped=stats.shipped,
        tasks_done=stats.tasks_done,
        tasks_total=stats.tasks_total,
    )


def _monday(week_start: date) -> date:
    if week_start.weekday() != 0:
        raise ValidationException(
            "Weeks are identified by their Monday.", field="week_start"
        )
    return week_start


@router.get("/organizations/{organization_id}/teams", tags=["teams"])
async def team_list(access: OrgMember, session: DBSession) -> list[TeamResponse]:
    rows = await TeamService(session).list_teams(access)
    return [
        TeamResponse(
            id=row.team.id,
            name=row.team.name,
            description=row.team.description,
            lead=user_summary(row.team.lead) if row.team.lead else None,
            member_count=row.member_count,
            is_member=row.is_member,
            is_lead=row.is_lead,
        )
        for row in rows
    ]


@router.post(
    "/organizations/{organization_id}/teams",
    status_code=status.HTTP_201_CREATED,
    tags=["teams"],
)
async def team_create(
    access: OrgManager, session: DBSession, data: TeamCreateRequest
) -> TeamDetailResponse:
    service = TeamService(session)
    team = await service.create_team(
        access,
        name=data.name,
        description=data.description,
        lead_user_id=data.lead_user_id,
        member_ids=data.member_ids,
    )
    await session.commit()
    return await _team_detail(service, access, team)


@router.get("/organizations/{organization_id}/teams/{team_id}", tags=["teams"])
async def team_get(
    access: OrgMember, session: DBSession, team_id: uuid.UUID
) -> TeamDetailResponse:
    service = TeamService(session)
    team = await service.get_team(access.organization_id, team_id)
    return await _team_detail(service, access, team)


@router.patch("/organizations/{organization_id}/teams/{team_id}", tags=["teams"])
async def team_update(
    access: OrgManager, session: DBSession, team_id: uuid.UUID, data: TeamUpdateRequest
) -> TeamDetailResponse:
    service = TeamService(session)
    team = await service.update_team(
        access, team_id, data.model_dump(exclude_unset=True)
    )
    await session.commit()
    return await _team_detail(service, access, team)


@router.delete(
    "/organizations/{organization_id}/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["teams"],
)
async def team_delete(
    access: OrgManager, session: DBSession, team_id: uuid.UUID
) -> None:
    await TeamService(session).delete_team(access, team_id)
    await session.commit()


@router.put(
    "/organizations/{organization_id}/teams/{team_id}/members/{user_id}",
    tags=["teams"],
)
async def team_member_add(
    access: OrgManager, session: DBSession, team_id: uuid.UUID, user_id: uuid.UUID
) -> TeamDetailResponse:
    service = TeamService(session)
    team = await service.add_member(access, team_id, user_id)
    await session.commit()
    return await _team_detail(service, access, team)


@router.delete(
    "/organizations/{organization_id}/teams/{team_id}/members/{user_id}",
    tags=["teams"],
)
async def team_member_remove(
    access: OrgManager, session: DBSession, team_id: uuid.UUID, user_id: uuid.UUID
) -> TeamDetailResponse:
    service = TeamService(session)
    team = await service.remove_member(access, team_id, user_id)
    await session.commit()
    return await _team_detail(service, access, team)


@router.get(
    "/organizations/{organization_id}/teams/{team_id}/weeks/{week_start}",
    tags=["teams"],
)
async def team_week_get(
    access: OrgMember, session: DBSession, team_id: uuid.UUID, week_start: date
) -> TeamWeekResponse:
    """The team's week at a glance: who has submitted, what's approved, task
    progress and whether each main task shipped. Drafts show as drafts only."""
    service = TeamService(session)
    team = await service.get_team(access.organization_id, team_id)
    rows = await service.team_week(access, team, _monday(week_start))
    stats = summarize_week(
        week_start, len(rows), [row.plan for row in rows if row.plan is not None]
    )
    return TeamWeekResponse(
        team=TeamRef(id=team.id, name=team.name),
        lead=user_summary(team.lead) if team.lead else None,
        week_start=week_start,
        viewer_is_lead=team.lead_user_id == access.user_id,
        stats=_stats(stats),
        members=[
            TeamWeekMember(
                member=user_summary(row.member),
                is_lead=row.is_lead,
                plan=plan_summary(row.plan, access.user_id) if row.plan else None,
            )
            for row in rows
        ],
    )


@router.get("/organizations/{organization_id}/teams/{team_id}/history", tags=["teams"])
async def team_history(
    access: OrgMember,
    session: DBSession,
    team_id: uuid.UUID,
    weeks: Annotated[int, Query(ge=1, le=26)] = 8,
    until: Annotated[
        date | None,
        Query(description="Last week to include (any day in it); defaults to now."),
    ] = None,
) -> TeamHistoryResponse:
    service = TeamService(session)
    team = await service.get_team(access.organization_id, team_id)
    history = await service.team_history(
        access,
        team,
        last_week=week_start_of(until) if until else current_week_start(),
        weeks=weeks,
    )
    return TeamHistoryResponse(
        team=TeamRef(id=team.id, name=team.name),
        weeks=[
            TeamHistoryWeek(week_start=week.week_start, **_stats(week).model_dump())
            for week in history
        ],
    )
