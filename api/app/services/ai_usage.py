import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AIErrorType, AIFeature, AIOutcome
from app.models import AIUsageEvent, Organization, User


@dataclass(frozen=True)
class UsageTotals:
    calls: int
    succeeded: int
    failed: int
    rate_limited: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: int | None


@dataclass(frozen=True)
class OrganizationUsage:
    organization_id: uuid.UUID
    organization_name: str
    totals: UsageTotals
    last_call_at: datetime | None


@dataclass(frozen=True)
class FeatureUsage:
    feature: AIFeature
    totals: UsageTotals


@dataclass(frozen=True)
class DayUsage:
    day: date
    succeeded: int
    failed: int
    rate_limited: int


@dataclass(frozen=True)
class ErrorTypeCount:
    error_type: AIErrorType
    count: int


@dataclass(frozen=True)
class UsageEventRow:
    event: AIUsageEvent
    organization_name: str
    user_email: str | None


def _totals_columns() -> tuple[ColumnElement[Any], ...]:
    """Aggregate columns read back by `_totals`, in this order."""
    outcome = AIUsageEvent.outcome
    return (
        func.count(),
        func.count().filter(outcome == "success"),
        func.count().filter(outcome == "failed"),
        func.count().filter(outcome == "rate_limited"),
        func.coalesce(func.sum(AIUsageEvent.input_tokens), 0),
        func.coalesce(func.sum(AIUsageEvent.output_tokens), 0),
        func.avg(AIUsageEvent.latency_ms),
    )


def _totals(row: Sequence[Any]) -> UsageTotals:
    calls, succeeded, failed, rate_limited, input_tokens, output_tokens, latency = row
    return UsageTotals(
        calls=int(calls),
        succeeded=int(succeeded),
        failed=int(failed),
        rate_limited=int(rate_limited),
        input_tokens=int(input_tokens),
        output_tokens=int(output_tokens),
        avg_latency_ms=round(float(latency)) if latency is not None else None,
    )


class AIUsageService:
    """The AI usage log: one content-free row per call, per organization."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        feature: AIFeature,
        outcome: AIOutcome,
        model_name: str,
        error_type: AIErrorType | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> AIUsageEvent:
        event = AIUsageEvent(
            organization_id=organization_id,
            user_id=user_id,
            feature=feature,
            outcome=outcome,
            error_type=error_type,
            model_name=model_name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def recent_requests(self, user_id: uuid.UUID, *, since: datetime) -> int:
        """Calls this user made since `since`, not counting ones we throttled
        ourselves (those never reached the provider)."""
        count = await self.session.scalar(
            select(func.count())
            .select_from(AIUsageEvent)
            .where(
                AIUsageEvent.user_id == user_id,
                AIUsageEvent.created_at >= since,
                AIUsageEvent.error_type.is_distinct_from("throttled"),
            )
        )
        return count or 0

    # --- Staff reporting -------------------------------------------------------------

    async def totals(
        self, *, since: datetime, organization_id: uuid.UUID | None = None
    ) -> UsageTotals:
        stmt = select(*_totals_columns()).where(AIUsageEvent.created_at >= since)
        if organization_id is not None:
            stmt = stmt.where(AIUsageEvent.organization_id == organization_id)
        row = (await self.session.execute(stmt)).one()
        return _totals(row)

    async def by_organization(self, *, since: datetime) -> list[OrganizationUsage]:
        rows = await self.session.execute(
            select(
                AIUsageEvent.organization_id,
                Organization.name,
                func.max(AIUsageEvent.created_at),
                *_totals_columns(),
            )
            .join(Organization, Organization.id == AIUsageEvent.organization_id)
            .where(AIUsageEvent.created_at >= since)
            .group_by(AIUsageEvent.organization_id, Organization.name)
            .order_by(func.count().desc())
        )
        return [
            OrganizationUsage(
                organization_id=row[0],
                organization_name=row[1],
                last_call_at=row[2],
                totals=_totals(row[3:]),
            )
            for row in rows
        ]

    async def by_feature(self, *, since: datetime) -> list[FeatureUsage]:
        rows = await self.session.execute(
            select(AIUsageEvent.feature, *_totals_columns())
            .where(AIUsageEvent.created_at >= since)
            .group_by(AIUsageEvent.feature)
            .order_by(AIUsageEvent.feature)
        )
        return [FeatureUsage(feature=row[0], totals=_totals(row[1:])) for row in rows]

    async def by_day(self, *, since: datetime, days: int) -> list[DayUsage]:
        day = cast(AIUsageEvent.created_at, Date)
        outcome = AIUsageEvent.outcome
        rows = await self.session.execute(
            select(
                day,
                func.count().filter(outcome == "success"),
                func.count().filter(outcome == "failed"),
                func.count().filter(outcome == "rate_limited"),
            )
            .where(AIUsageEvent.created_at >= since)
            .group_by(day)
        )
        by_day = {row[0]: row for row in rows}
        first_day = since.date()
        series: list[DayUsage] = []
        for offset in range(days):
            current = first_day + timedelta(days=offset)
            row = by_day.get(current)
            series.append(
                DayUsage(
                    day=current,
                    succeeded=row[1] if row else 0,
                    failed=row[2] if row else 0,
                    rate_limited=row[3] if row else 0,
                )
            )
        return series

    async def by_error_type(self, *, since: datetime) -> list[ErrorTypeCount]:
        rows = await self.session.execute(
            select(AIUsageEvent.error_type, func.count())
            .where(
                AIUsageEvent.created_at >= since,
                AIUsageEvent.error_type.is_not(None),
            )
            .group_by(AIUsageEvent.error_type)
            .order_by(func.count().desc())
        )
        return [
            ErrorTypeCount(error_type=error_type, count=count)
            for error_type, count in rows.tuples()
            if error_type is not None
        ]

    async def list_events(
        self,
        *,
        organization_id: uuid.UUID | None,
        outcome: AIOutcome | None,
        feature: AIFeature | None,
        limit: int,
        offset: int,
    ) -> tuple[list[UsageEventRow], int]:
        conditions: list[ColumnElement[bool]] = []
        if organization_id is not None:
            conditions.append(AIUsageEvent.organization_id == organization_id)
        if outcome is not None:
            conditions.append(AIUsageEvent.outcome == outcome)
        if feature is not None:
            conditions.append(AIUsageEvent.feature == feature)

        total = await self.session.scalar(
            select(func.count()).select_from(AIUsageEvent).where(*conditions)
        )
        rows = await self.session.execute(
            select(AIUsageEvent, Organization.name, User.email)
            .join(Organization, Organization.id == AIUsageEvent.organization_id)
            .outerjoin(User, User.id == AIUsageEvent.user_id)
            .where(*conditions)
            .order_by(AIUsageEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = [
            UsageEventRow(event=event, organization_name=name, user_email=email)
            for event, name, email in rows.tuples()
        ]
        return items, total or 0
