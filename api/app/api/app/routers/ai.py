from fastapi import APIRouter

from app.ai.provider import AIModel
from app.ai.service import AIFailure, AIService, ReviewTaskInput
from app.api.app.access import OrgMember
from app.api.app.schemas import (
    PlanDraftRequest,
    PlanDraftResponse,
    PlanReviewRequest,
    PlanReviewResponse,
    ReviewFindingResponse,
)
from app.database import DBSession

router = APIRouter()


@router.post("/organizations/{organization_id}/ai/plan-review", tags=["ai"])
async def ai_plan_review(
    access: OrgMember, session: DBSession, model: AIModel, data: PlanReviewRequest
) -> PlanReviewResponse:
    """Review the plan in the editor the way a demanding lead would. Each
    finding names a task and comes with a rewrite the member can apply. The
    review is advice only: it never changes or approves the plan."""
    result = await AIService(session, model).review_plan(
        access,
        week_start=data.week_start,
        why_it_matters=data.why_it_matters,
        tasks=[
            ReviewTaskInput(key=task.key, kind=task.kind, title=task.title)
            for task in data.tasks
        ],
    )
    # The usage event is committed whatever the outcome.
    await session.commit()
    if isinstance(result, AIFailure):
        raise result.to_exception()
    return PlanReviewResponse(
        verdict=result.verdict,
        summary=result.summary,
        findings=[
            ReviewFindingResponse(
                task_key=finding.task_key,
                category=finding.category,
                problem=finding.problem,
                suggested_rewrite=finding.suggested_rewrite,
                action=finding.action,
            )
            for finding in result.findings
        ],
    )


@router.post("/organizations/{organization_id}/ai/plan-draft", tags=["ai"])
async def ai_plan_draft(
    access: OrgMember, session: DBSession, model: AIModel, data: PlanDraftRequest
) -> PlanDraftResponse:
    """Turn a brain dump into a suggested plan for the editor. Nothing is
    saved: the member reviews and edits the draft, then saves it themselves."""
    result = await AIService(session, model).draft_plan(
        access, week_start=data.week_start, notes=data.notes
    )
    await session.commit()
    if isinstance(result, AIFailure):
        raise result.to_exception()
    return PlanDraftResponse.model_validate(result.model_dump())
