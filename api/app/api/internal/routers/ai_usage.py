import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.internal.access import CurrentInternalUser
from app.api.internal.schemas import (
    AIUsageByFeature,
    AIUsageByOrganization,
    AIUsageDay,
    AIUsageErrorCount,
    AIUsageEventResponse,
    AIUsageEventsResponse,
    AIUsageSummaryResponse,
    AIUsageTotals,
)
from app.config import settings
from app.database import DBSession
from app.domain import AIFeature, AIOutcome, utcnow
from app.services.ai_usage import AIUsageService

router = APIRouter()


@router.get("/ai-usage", tags=["ai-usage"])
async def ai_usage_summary(
    current_user: CurrentInternalUser,
    session: DBSession,
    days: int = Query(30, ge=1, le=90),
) -> AIUsageSummaryResponse:
    """What the AI features cost and where they break: calls, failures and
    rate limits per organization, per feature and per day."""
    service = AIUsageService(session)
    # Whole days, today included, so the daily chart has no partial first bar.
    first_day = utcnow().date() - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=UTC)
    return AIUsageSummaryResponse(
        days=days,
        model_name=settings.AI_MODEL,
        totals=AIUsageTotals.model_validate(await service.totals(since=since)),
        by_organization=[
            AIUsageByOrganization(
                organization_id=row.organization_id,
                organization_name=row.organization_name,
                last_call_at=row.last_call_at,
                totals=AIUsageTotals.model_validate(row.totals),
            )
            for row in await service.by_organization(since=since)
        ],
        by_feature=[
            AIUsageByFeature(
                feature=row.feature,
                totals=AIUsageTotals.model_validate(row.totals),
            )
            for row in await service.by_feature(since=since)
        ],
        by_day=[
            AIUsageDay(
                day=row.day,
                succeeded=row.succeeded,
                failed=row.failed,
                rate_limited=row.rate_limited,
            )
            for row in await service.by_day(since=since, days=days)
        ],
        by_error_type=[
            AIUsageErrorCount(error_type=row.error_type, count=row.count)
            for row in await service.by_error_type(since=since)
        ],
    )


@router.get("/ai-usage/events", tags=["ai-usage"])
async def ai_usage_events(
    current_user: CurrentInternalUser,
    session: DBSession,
    organization_id: Annotated[uuid.UUID | None, Query()] = None,
    outcome: Annotated[AIOutcome | None, Query()] = None,
    feature: Annotated[AIFeature | None, Query()] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AIUsageEventsResponse:
    """Individual AI calls, newest first. Metadata only: no prompts or output."""
    rows, total = await AIUsageService(session).list_events(
        organization_id=organization_id,
        outcome=outcome,
        feature=feature,
        limit=limit,
        offset=offset,
    )
    return AIUsageEventsResponse(
        items=[
            AIUsageEventResponse(
                id=row.event.id,
                created_at=row.event.created_at,
                organization_id=row.event.organization_id,
                organization_name=row.organization_name,
                user_email=row.user_email,
                feature=row.event.feature,
                outcome=row.event.outcome,
                error_type=row.event.error_type,
                model_name=row.event.model_name,
                latency_ms=row.event.latency_ms,
                input_tokens=row.event.input_tokens,
                output_tokens=row.event.output_tokens,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
