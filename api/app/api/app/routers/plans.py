import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.app.access import OrgMember
from app.api.app.presenters import plan_response, plan_summary, user_summary
from app.api.app.schemas import (
    CompletePlanRequest,
    MyWeekResponse,
    PlanContentRequest,
    PlanCreateRequest,
    PlanListResponse,
    PlanResponse,
    ReturnPlanRequest,
    ReviewDecisionRequest,
    ReviewQueueItem,
    TaskStatusRequest,
    TeamRef,
)
from app.database import DBSession
from app.exceptions import ValidationException
from app.models import WeeklyPlan
from app.services.plans import PlanContent, PlanService, TaskDraft
from app.tenancy import OrgAccess

router = APIRouter()


def _content(data: PlanContentRequest) -> PlanContent:
    return PlanContent(
        main_task=data.main_task,
        why_it_matters=data.why_it_matters,
        sub_goals=[TaskDraft(id=task.id, title=task.title) for task in data.sub_goals],
        go_to_market=[
            TaskDraft(id=task.id, title=task.title) for task in data.go_to_market
        ],
    )


async def _respond(
    service: PlanService, access: OrgAccess, plan: WeeklyPlan
) -> PlanResponse:
    return plan_response(plan, await service.permissions(access, plan))


# --- The caller's own plans ---------------------------------------------------------------


@router.get("/organizations/{organization_id}/me/weeks/{week_start}", tags=["plans"])
async def my_week_get(
    access: OrgMember, session: DBSession, week_start: date
) -> MyWeekResponse:
    """The caller's plan for a week (null if not started yet) and who can
    approve it."""
    if week_start.weekday() != 0:
        raise ValidationException(
            "Weeks are identified by their Monday.", field="week_start"
        )
    service = PlanService(session)
    plan = await service.plan_for_week(access, week_start)
    reviewers = await service.reviewers_for(access.organization_id, access.user_id)
    return MyWeekResponse(
        week_start=week_start,
        plan=await _respond(service, access, plan) if plan else None,
        reviewers=[user_summary(user) for user in reviewers],
    )


@router.get("/organizations/{organization_id}/me/plans", tags=["plans"])
async def my_plan_list(
    access: OrgMember,
    session: DBSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PlanListResponse:
    """The caller's plans in this organization, newest week first."""
    plans, total = await PlanService(session).list_own_plans(
        access, limit=limit, offset=offset
    )
    return PlanListResponse(
        items=[plan_summary(plan, access.user_id) for plan in plans],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/organizations/{organization_id}/plans",
    status_code=status.HTTP_201_CREATED,
    tags=["plans"],
)
async def plan_create(
    access: OrgMember, session: DBSession, data: PlanCreateRequest
) -> PlanResponse:
    """Start the caller's plan for a week, as a draft."""
    service = PlanService(session)
    plan = await service.create_plan(access, data.week_start, _content(data))
    await session.commit()
    return await _respond(service, access, plan)


@router.get("/organizations/{organization_id}/plans/{plan_id}", tags=["plans"])
async def plan_get(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID
) -> PlanResponse:
    service = PlanService(session)
    plan = await service.get_visible_plan(access, plan_id)
    return await _respond(service, access, plan)


@router.put("/organizations/{organization_id}/plans/{plan_id}", tags=["plans"])
async def plan_update(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID, data: PlanContentRequest
) -> PlanResponse:
    """Replace a draft's content. Tasks sent with their id keep their state."""
    service = PlanService(session)
    plan = await service.update_plan(access, plan_id, _content(data))
    await session.commit()
    return await _respond(service, access, plan)


@router.delete(
    "/organizations/{organization_id}/plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["plans"],
)
async def plan_delete(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID
) -> None:
    await PlanService(session).delete_plan(access, plan_id)
    await session.commit()


# --- Lifecycle ------------------------------------------------------------------------------


@router.post("/organizations/{organization_id}/plans/{plan_id}/submit", tags=["plans"])
async def plan_submit(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID
) -> PlanResponse:
    service = PlanService(session)
    plan = await service.submit(access, plan_id)
    await session.commit()
    return await _respond(service, access, plan)


@router.post(
    "/organizations/{organization_id}/plans/{plan_id}/withdraw", tags=["plans"]
)
async def plan_withdraw(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID
) -> PlanResponse:
    """Take a submitted plan back to draft before it's reviewed."""
    service = PlanService(session)
    plan = await service.withdraw(access, plan_id)
    await session.commit()
    return await _respond(service, access, plan)


@router.post(
    "/organizations/{organization_id}/plans/{plan_id}/approve", tags=["reviews"]
)
async def plan_approve(
    access: OrgMember,
    session: DBSession,
    plan_id: uuid.UUID,
    data: ReviewDecisionRequest,
) -> PlanResponse:
    """Approve a submitted plan. Only the lead of a team the author is on."""
    service = PlanService(session)
    plan = await service.approve(access, plan_id, data.comment)
    await session.commit()
    return await _respond(service, access, plan)


@router.post(
    "/organizations/{organization_id}/plans/{plan_id}/return", tags=["reviews"]
)
async def plan_return(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID, data: ReturnPlanRequest
) -> PlanResponse:
    """Send a submitted plan back to draft with a comment for the author."""
    service = PlanService(session)
    plan = await service.return_to_author(access, plan_id, data.comment)
    await session.commit()
    return await _respond(service, access, plan)


@router.post(
    "/organizations/{organization_id}/plans/{plan_id}/complete", tags=["plans"]
)
async def plan_complete(
    access: OrgMember, session: DBSession, plan_id: uuid.UUID, data: CompletePlanRequest
) -> PlanResponse:
    """Close the week: record whether the main task shipped."""
    service = PlanService(session)
    plan = await service.complete(
        access,
        plan_id,
        main_task_shipped=data.main_task_shipped,
        outcome_note=data.outcome_note,
    )
    await session.commit()
    return await _respond(service, access, plan)


@router.patch(
    "/organizations/{organization_id}/plans/{plan_id}/tasks/{task_id}",
    tags=["plans"],
)
async def plan_task_update(
    access: OrgMember,
    session: DBSession,
    plan_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskStatusRequest,
) -> PlanResponse:
    """Tick a task off (or untick it) during the week."""
    service = PlanService(session)
    plan = await service.set_task_status(access, plan_id, task_id, data.status)
    await session.commit()
    return await _respond(service, access, plan)


# --- Review queue ---------------------------------------------------------------------------


@router.get("/organizations/{organization_id}/reviews", tags=["reviews"])
async def review_queue(access: OrgMember, session: DBSession) -> list[ReviewQueueItem]:
    """Submitted plans waiting for the caller's review, oldest first."""
    service = PlanService(session)
    plans = await service.review_queue(access)
    teams = await service.led_teams_by_author(
        access, list({plan.user_id for plan in plans})
    )
    return [
        ReviewQueueItem(
            plan=plan_summary(plan, access.user_id),
            teams=[
                TeamRef(id=team.id, name=team.name)
                for team in teams.get(plan.user_id, [])
            ],
        )
        for plan in plans
    ]
