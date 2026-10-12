"""Builders for test data, and a client wrapper that acts as one user."""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import OrgRole, PlanStatus, current_week_start, utcnow
from app.models import (
    Membership,
    Organization,
    PlanTask,
    Team,
    TeamMembership,
    User,
    WeeklyPlan,
)
from app.security import (
    JWT_AUDIENCE_APP,
    JWT_AUDIENCE_INTERNAL,
    generate_jwt_token,
    hash_password,
)

PASSWORD = "correct-horse-1"
# Argon2 is deliberately slow; hash once and share it across test users.
PASSWORD_HASH = hash_password(PASSWORD)
_sequence = itertools.count(1)


async def make_user(
    db: AsyncSession,
    first_name: str = "Test",
    *,
    email: str | None = None,
    staff: bool = False,
    active: bool = True,
) -> User:
    n = next(_sequence)
    user = User(
        first_name=first_name,
        last_name=f"User{n}",
        email=email or f"{first_name.lower()}{n}@example.com",
        password=PASSWORD_HASH,
        is_active=active,
        is_platform_staff=staff,
    )
    db.add(user)
    await db.commit()
    return user


async def make_org(db: AsyncSession, name: str, *, owner: User) -> Organization:
    organization = Organization(name=name)
    db.add(organization)
    await db.flush()
    db.add(Membership(organization_id=organization.id, user_id=owner.id, role="owner"))
    await db.commit()
    return organization


async def add_member(
    db: AsyncSession, organization: Organization, user: User, role: OrgRole = "member"
) -> Membership:
    membership = Membership(organization_id=organization.id, user_id=user.id, role=role)
    db.add(membership)
    await db.commit()
    return membership


async def make_team(
    db: AsyncSession,
    organization: Organization,
    name: str,
    *,
    lead: User | None,
    members: Sequence[User] = (),
) -> Team:
    team = Team(
        organization_id=organization.id,
        name=name,
        lead_user_id=lead.id if lead else None,
    )
    db.add(team)
    await db.flush()
    people = {user.id: user for user in [*members, *([lead] if lead else [])]}
    for user_id in people:
        db.add(
            TeamMembership(
                organization_id=organization.id, team_id=team.id, user_id=user_id
            )
        )
    await db.commit()
    return team


async def make_plan(
    db: AsyncSession,
    organization: Organization,
    author: User,
    *,
    week_start: date | None = None,
    status: PlanStatus = "draft",
    main_task: str = "Checkout handles expired cards, confirmed on staging",
    why_it_matters: str | None = "Expired cards fail renewals silently.",
    sub_goals: Sequence[str] = ("Retry schedule covered by integration tests",),
    go_to_market: Sequence[str] = ("Changelog entry published",),
    main_task_shipped: bool | None = None,
    outcome_note: str | None = None,
) -> WeeklyPlan:
    tasks = [PlanTask(kind="main", title=main_task, position=0)]
    for title in sub_goals:
        tasks.append(PlanTask(kind="sub_goal", title=title, position=len(tasks)))
    for title in go_to_market:
        tasks.append(PlanTask(kind="go_to_market", title=title, position=len(tasks)))
    plan = WeeklyPlan(
        organization_id=organization.id,
        user_id=author.id,
        week_start=week_start or current_week_start(),
        status=status,
        why_it_matters=why_it_matters,
        tasks=tasks,
        submitted_at=utcnow() if status != "draft" else None,
        main_task_shipped=main_task_shipped,
        outcome_note=outcome_note,
    )
    db.add(plan)
    await db.commit()
    return plan


@dataclass
class Actor:
    """Calls the API as one user. Identity travels in the Access-Token header,
    so a single test can switch between several users freely."""

    client: AsyncClient
    user: User
    surface: str = "app"

    @property
    def headers(self) -> dict[str, str]:
        audience = (
            JWT_AUDIENCE_INTERNAL if self.surface == "internal" else JWT_AUDIENCE_APP
        )
        token = generate_jwt_token({"sub": str(self.user.id)}, audience=audience)
        return {"Access-Token": f"Bearer {token}"}

    async def get(self, path: str, **kwargs: Any) -> Response:
        return await self.client.get(self._url(path), headers=self.headers, **kwargs)

    async def post(self, path: str, json: Any = None, **kwargs: Any) -> Response:
        return await self.client.post(
            self._url(path),
            json=json if json is not None else {},
            headers=self.headers,
            **kwargs,
        )

    async def put(self, path: str, json: Any = None, **kwargs: Any) -> Response:
        return await self.client.put(
            self._url(path),
            json=json if json is not None else {},
            headers=self.headers,
            **kwargs,
        )

    async def patch(self, path: str, json: Any = None, **kwargs: Any) -> Response:
        return await self.client.patch(
            self._url(path),
            json=json if json is not None else {},
            headers=self.headers,
            **kwargs,
        )

    async def delete(self, path: str, **kwargs: Any) -> Response:
        return await self.client.delete(self._url(path), headers=self.headers, **kwargs)

    def _url(self, path: str) -> str:
        return f"/{self.surface}{path}"


def error_code(response: Response) -> str:
    """The `type` of the first error in the API's error body."""
    return response.json()["detail"][0]["type"]


def plan_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "main_task": "Refunds post to the ledger within a minute in production",
        "why_it_matters": "Support issues refunds by hand today.",
        "sub_goals": [{"title": "Partial refunds supported in the dialog"}],
        "go_to_market": [{"title": "Changelog entry for dashboard refunds"}],
    }
    body.update(overrides)
    return body
