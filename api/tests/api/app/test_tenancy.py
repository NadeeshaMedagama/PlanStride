"""Organization isolation, checked the way a reviewer would: by calling every
endpoint with another organization's ids."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain import current_week_start, utcnow
from app.models import Invitation, PlanTask, WeeklyPlan
from app.security import hash_invite_token
from tests.factories import plan_body

WEEK = current_week_start().isoformat()

# Every organization-scoped endpoint, aimed at Globex. Placeholders are filled
# from the world fixture.
CROSS_ORG_REQUESTS = [
    ("get", "/organizations/{globex}", None),
    ("patch", "/organizations/{globex}", {"name": "Taken over"}),
    ("get", "/organizations/{globex}/members", None),
    ("patch", "/organizations/{globex}/members/{carol}", {"role": "admin"}),
    ("delete", "/organizations/{globex}/members/{carol}", None),
    ("get", "/organizations/{globex}/invitations", None),
    ("post", "/organizations/{globex}/invitations", {"role": "admin"}),
    ("delete", "/organizations/{globex}/invitations/{any_id}", None),
    ("get", "/organizations/{globex}/teams", None),
    ("post", "/organizations/{globex}/teams", {"name": "Moles"}),
    ("get", "/organizations/{globex}/teams/{gamma}", None),
    ("patch", "/organizations/{globex}/teams/{gamma}", {"name": "Renamed"}),
    ("delete", "/organizations/{globex}/teams/{gamma}", None),
    ("put", "/organizations/{globex}/teams/{gamma}/members/{carol}", None),
    ("delete", "/organizations/{globex}/teams/{gamma}/members/{carol}", None),
    ("get", "/organizations/{globex}/teams/{gamma}/weeks/{week}", None),
    ("get", "/organizations/{globex}/teams/{gamma}/history", None),
    ("get", "/organizations/{globex}/me/weeks/{week}", None),
    ("get", "/organizations/{globex}/me/plans", None),
    ("post", "/organizations/{globex}/plans", {**plan_body(), "week_start": WEEK}),
    ("get", "/organizations/{globex}/plans/{carol_plan}", None),
    ("put", "/organizations/{globex}/plans/{carol_plan}", plan_body()),
    ("delete", "/organizations/{globex}/plans/{carol_plan}", None),
    ("post", "/organizations/{globex}/plans/{carol_plan}/submit", None),
    ("post", "/organizations/{globex}/plans/{carol_plan}/withdraw", None),
    ("post", "/organizations/{globex}/plans/{carol_plan}/approve", {}),
    ("post", "/organizations/{globex}/plans/{carol_plan}/return", {"comment": "No"}),
    (
        "post",
        "/organizations/{globex}/plans/{carol_plan}/complete",
        {"main_task_shipped": True},
    ),
    (
        "patch",
        "/organizations/{globex}/plans/{carol_plan}/tasks/{carol_task}",
        {"status": "done"},
    ),
    ("get", "/organizations/{globex}/reviews", None),
    (
        "post",
        "/organizations/{globex}/ai/plan-review",
        {"week_start": WEEK, "tasks": [{"key": "a", "kind": "main", "title": "Ship"}]},
    ),
    (
        "post",
        "/organizations/{globex}/ai/plan-draft",
        {"week_start": WEEK, "notes": "finish the billing page this week"},
    ),
]


def _fill(path: str, world, carol_task) -> str:
    return path.format(
        globex=world.globex.id,
        acme=world.acme.id,
        carol=world.carol.id,
        gamma=world.gamma.id,
        carol_plan=world.carol_plan.id,
        carol_task=carol_task,
        any_id="00000000-0000-4000-8000-000000000000",
        week=WEEK,
    )


async def _carol_task_id(db, world):
    return await db.scalar(
        select(PlanTask.id).where(PlanTask.plan_id == world.carol_plan.id).limit(1)
    )


@pytest.mark.parametrize(("method", "path", "body"), CROSS_ORG_REQUESTS)
async def test_other_organizations_resources_are_invisible(
    world, db, method, path, body
):
    """Even Acme's owner gets the same 404 as for an id that doesn't exist."""
    actor = world.as_(world.owner)
    url = _fill(path, world, await _carol_task_id(db, world))
    call = getattr(actor, method)
    response = await (call(url, json=body) if body is not None else call(url))

    assert response.status_code == 404, response.text
    assert response.json()["detail"][0]["msg"] == "Organization not found"


async def test_cross_org_attempts_change_nothing(world, db):
    actor = world.as_(world.owner)
    task = await _carol_task_id(db, world)
    for method, path, body in CROSS_ORG_REQUESTS:
        call = getattr(actor, method)
        url = _fill(path, world, task)
        await (call(url, json=body) if body is not None else call(url))

    await db.refresh(world.globex)
    plan = await db.get(WeeklyPlan, world.carol_plan.id, populate_existing=True)
    assert world.globex.name == "Globex"
    assert plan is not None and plan.status == "submitted"
    invitations = await db.scalar(
        select(Invitation.id).where(Invitation.organization_id == world.globex.id)
    )
    assert invitations is None


# Mixing an organization the caller IS in with another organization's ids.
async def test_foreign_plan_id_through_own_organization(world):
    actor = world.as_(world.owner)
    base = f"/organizations/{world.acme.id}/plans/{world.carol_plan.id}"
    for response in (
        await actor.get(base),
        await actor.put(base, json=plan_body()),
        await actor.post(f"{base}/approve", json={}),
        await actor.post(f"{base}/return", json={"comment": "No"}),
        await actor.delete(base),
    ):
        assert response.status_code == 404
        assert response.json()["detail"][0]["msg"] == "Plan not found"


async def test_foreign_team_and_member_ids_through_own_organization(world):
    actor = world.as_(world.owner)
    acme = f"/organizations/{world.acme.id}"

    assert (await actor.get(f"{acme}/teams/{world.gamma.id}")).status_code == 404
    assert (
        await actor.patch(f"{acme}/members/{world.carol.id}", json={"role": "admin"})
    ).status_code == 404
    # A stranger can't be put on an Acme team either.
    response = await actor.put(
        f"{acme}/teams/{world.alpha.id}/members/{world.carol.id}"
    )
    assert response.status_code == 400
    assert response.json()["detail"][0]["loc"] == ["body", "member_ids"]


async def test_foreign_task_id_on_own_plan(world, db):
    actor = world.as_(world.alice)
    task = await _carol_task_id(db, world)
    response = await actor.patch(
        f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}/tasks/{task}",
        json={"status": "done"},
    )
    assert response.status_code == 404
    assert response.json()["detail"][0]["msg"] == "Task not found"


async def test_foreign_invitation_cannot_be_revoked(world, db):
    invitation = Invitation(
        organization_id=world.globex.id,
        role="member",
        token_hash=hash_invite_token("globex-secret"),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()

    response = await world.as_(world.owner).delete(
        f"/organizations/{world.acme.id}/invitations/{invitation.id}"
    )
    assert response.status_code == 404
    await db.refresh(invitation)
    assert invitation.revoked_at is None


async def test_organization_list_only_shows_own_memberships(world):
    response = await world.as_(world.alice).get("/organizations")
    assert response.status_code == 200
    assert [org["name"] for org in response.json()] == ["Acme"]


async def test_reviews_queue_never_includes_other_organizations(world):
    response = await world.as_(world.lead_b).get(
        f"/organizations/{world.acme.id}/reviews"
    )
    assert response.status_code == 404

    response = await world.as_(world.lead).get(
        f"/organizations/{world.acme.id}/reviews"
    )
    authors = {item["plan"]["author"]["id"] for item in response.json()}
    assert authors == {str(world.alice.id)}


async def test_staff_flag_grants_nothing_in_customer_organizations(world):
    """Platform staff use the internal console; in the app they're a stranger."""
    response = await world.as_(world.staff).get(f"/organizations/{world.acme.id}")
    assert response.status_code == 404


async def test_unauthenticated_requests_are_rejected(world, async_client):
    for path in (
        "/organizations",
        f"/organizations/{world.acme.id}/teams",
        f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}",
    ):
        response = await async_client.get(f"/app{path}")
        assert response.status_code == 401
