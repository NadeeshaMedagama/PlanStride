"""Turn ORM objects into app API responses.

Kept in one place because the same rule has to hold everywhere a plan is
listed: someone else's draft shows its status but not its content.
"""

import uuid

from app.api.app.schemas import (
    InvitationResponse,
    PlanPermissionsResponse,
    PlanResponse,
    PlanSummaryResponse,
    PlanTaskResponse,
    UserSummary,
)
from app.models import Invitation, User, WeeklyPlan
from app.services.organizations import invitation_status
from app.services.plans import PlanPermissions


def user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )


def _main_task_title(plan: WeeklyPlan) -> str:
    return next((task.title for task in plan.tasks if task.kind == "main"), "")


def plan_response(plan: WeeklyPlan, permissions: PlanPermissions) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        week_start=plan.week_start,
        status=plan.status,
        author=user_summary(plan.author),
        why_it_matters=plan.why_it_matters,
        tasks=[PlanTaskResponse.model_validate(task) for task in plan.tasks],
        tasks_done=sum(task.status == "done" for task in plan.tasks),
        tasks_total=len(plan.tasks),
        submitted_at=plan.submitted_at,
        reviewed_at=plan.reviewed_at,
        reviewed_by=user_summary(plan.reviewed_by) if plan.reviewed_by else None,
        review_decision=plan.review_decision,
        review_comment=plan.review_comment,
        completed_at=plan.completed_at,
        main_task_shipped=plan.main_task_shipped,
        outcome_note=plan.outcome_note,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        permissions=PlanPermissionsResponse.model_validate(permissions),
    )


def plan_summary(plan: WeeklyPlan, viewer_id: uuid.UUID) -> PlanSummaryResponse:
    private = plan.status == "draft" and plan.user_id != viewer_id
    return PlanSummaryResponse(
        id=plan.id,
        week_start=plan.week_start,
        status=plan.status,
        author=user_summary(plan.author),
        main_task=None if private else _main_task_title(plan),
        tasks_done=None if private else sum(t.status == "done" for t in plan.tasks),
        tasks_total=None if private else len(plan.tasks),
        main_task_shipped=plan.main_task_shipped,
        review_decision=plan.review_decision,
        submitted_at=plan.submitted_at,
    )


def invitation_response(invitation: Invitation) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        role=invitation.role,
        status=invitation_status(invitation),
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        created_by=user_summary(invitation.created_by)
        if invitation.created_by
        else None,
        accepted_by=user_summary(invitation.accepted_by)
        if invitation.accepted_by
        else None,
    )
