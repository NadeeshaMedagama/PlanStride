"""The internal console's API: staff only, and never customer content."""

from datetime import timedelta

from sqlalchemy import select

from app.domain import utcnow
from app.models import AIUsageEvent, User
from app.security import JWT_AUDIENCE_APP, generate_jwt_token
from tests.factories import PASSWORD, Actor, error_code, make_user

# --- Who gets in ----------------------------------------------------------------------------


async def test_customer_owners_and_admins_cannot_sign_in(world, async_client):
    for user in (world.owner, world.admin):
        response = await async_client.post(
            "/internal/auth", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == 401


async def test_staff_sign_in_and_deactivated_staff_cannot(world, async_client, db):
    ok = await async_client.post(
        "/internal/auth", json={"email": world.staff.email, "password": PASSWORD}
    )
    assert ok.status_code == 200
    assert "internal_access_token" in ok.cookies
    await db.refresh(world.staff)
    assert world.staff.last_login_at is not None

    retired = await make_user(db, "Retired", staff=True, active=False)
    refused = await async_client.post(
        "/internal/auth", json={"email": retired.email, "password": PASSWORD}
    )
    assert refused.status_code == 401


async def test_app_tokens_and_customer_tokens_are_refused(world, async_client):
    # A staff member's app-surface token is the wrong audience for /internal.
    app_token = generate_jwt_token(
        {"sub": str(world.staff.id)}, audience=JWT_AUDIENCE_APP
    )
    response = await async_client.get(
        "/internal/users", headers={"Access-Token": f"Bearer {app_token}"}
    )
    assert response.status_code == 401

    # A customer holding an internal-audience token is still not staff.
    customer = Actor(async_client, world.owner, surface="internal")
    response = await customer.get("/organizations")
    assert response.status_code == 403
    assert error_code(response) == "platform_staff_required"


async def test_every_internal_endpoint_requires_staff(world):
    customer = Actor(world.client, world.owner, surface="internal")
    for path in (
        "/overview",
        "/users",
        f"/users/{world.alice.id}",
        "/organizations",
        f"/organizations/{world.acme.id}",
        "/ai-usage",
        "/ai-usage/events",
    ):
        assert (await customer.get(path)).status_code == 403, path
    for path in (
        f"/organizations/{world.acme.id}/suspend",
        f"/organizations/{world.acme.id}/reinstate",
    ):
        assert (await customer.post(path)).status_code == 403, path


# --- Organizations ------------------------------------------------------------------------------


async def test_organization_list_has_counts_and_activity(world):
    response = await world.as_staff().get("/organizations")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    acme = next(org for org in body["items"] if org["name"] == "Acme")
    assert (acme["member_count"], acme["team_count"], acme["plan_count"]) == (6, 2, 1)
    assert [owner["email"] for owner in acme["owners"]] == [world.owner.email]
    assert acme["last_active_at"] is not None
    assert acme["suspended_at"] is None


async def test_organization_list_filters(world):
    staff = world.as_staff()
    await staff.post(f"/organizations/{world.globex.id}/suspend", json={})
    suspended = (
        await staff.get("/organizations", params={"status": "suspended"})
    ).json()
    searched = (await staff.get("/organizations", params={"search": "acm"})).json()
    assert [org["name"] for org in suspended["items"]] == ["Globex"]
    assert [org["name"] for org in searched["items"]] == ["Acme"]


async def test_staff_never_see_plan_content(world):
    """Data minimization: no internal response carries what customers wrote."""
    staff = world.as_staff()
    plan_text = "Checkout handles expired cards"
    responses = [
        await staff.get("/overview"),
        await staff.get("/organizations"),
        await staff.get(f"/organizations/{world.acme.id}"),
        await staff.get("/users"),
        await staff.get(f"/users/{world.alice.id}"),
        await staff.get("/ai-usage"),
        await staff.get("/ai-usage/events"),
    ]
    for response in responses:
        assert response.status_code == 200
        assert plan_text not in response.text

    detail = responses[2].json()
    assert detail["plans_by_status"] == {
        "draft": 0,
        "submitted": 1,
        "approved": 0,
        "done": 0,
    }
    assert {team["name"] for team in detail["teams"]} == {"Alpha", "Beta"}


async def test_suspend_and_reinstate(world):
    staff = world.as_staff()
    suspended = await staff.post(
        f"/organizations/{world.acme.id}/suspend", json={"reason": "Chargeback"}
    )
    assert suspended.status_code == 200
    assert suspended.json()["suspension_reason"] == "Chargeback"
    assert (
        await staff.post(f"/organizations/{world.acme.id}/suspend", json={})
    ).status_code == 409

    reinstated = await staff.post(f"/organizations/{world.acme.id}/reinstate")
    assert reinstated.json()["suspended_at"] is None
    assert (
        await staff.post(f"/organizations/{world.acme.id}/reinstate")
    ).status_code == 409


# --- Users -----------------------------------------------------------------------------------------


async def test_user_search_shows_memberships(world):
    response = await world.as_staff().get("/users", params={"search": "alice"})
    body = response.json()
    assert body["total"] == 1
    [alice] = body["items"]
    assert [(m["organization_name"], m["role"]) for m in alice["memberships"]] == [
        ("Acme", "member")
    ]
    assert alice["is_platform_staff"] is False
    assert "password" not in alice


async def test_search_treats_wildcards_literally(world):
    response = await world.as_staff().get("/users", params={"search": "%"})
    assert response.json()["total"] == 0


async def test_deactivating_a_user_locks_them_out_immediately(world):
    alice = world.as_(world.alice)
    assert (await alice.get("/users/self")).status_code == 200

    response = await world.as_staff().patch(
        f"/users/{world.alice.id}", json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    # The token Alice already holds stops working.
    assert (await alice.get("/users/self")).status_code == 401
    assert (await alice.get(f"/organizations/{world.acme.id}")).status_code == 401

    await world.as_staff().patch(f"/users/{world.alice.id}", json={"is_active": True})
    assert (await alice.get("/users/self")).status_code == 200


async def test_staff_cannot_deactivate_themselves_or_grant_staff(world, db):
    staff = world.as_staff()
    self_lockout = await staff.patch(
        f"/users/{world.staff.id}", json={"is_active": False}
    )
    assert self_lockout.status_code == 400

    promote = await staff.patch(
        f"/users/{world.alice.id}", json={"is_platform_staff": True, "is_admin": True}
    )
    assert promote.status_code == 200
    user = await db.scalar(
        select(User)
        .where(User.id == world.alice.id)
        .execution_options(populate_existing=True)
    )
    assert user is not None and user.is_platform_staff is False


async def test_staff_can_set_a_password_for_a_locked_out_user(world, async_client):
    response = await world.as_staff().post(
        f"/users/{world.alice.id}/change-password", json={"password": "brand-new-pass"}
    )
    assert response.status_code == 204
    login = await async_client.post(
        "/app/auth", json={"email": world.alice.email, "password": "brand-new-pass"}
    )
    assert login.status_code == 200


# --- AI usage --------------------------------------------------------------------------------------


async def test_ai_usage_summarizes_calls_failures_and_rate_limits(world, db):
    now = utcnow()
    rows = [
        (world.acme.id, "plan_review", "success", None, 1200, 300),
        (
            world.acme.id,
            "plan_review",
            "rate_limited",
            "provider_rate_limit",
            None,
            None,
        ),
        (world.acme.id, "plan_draft", "failed", "timeout", None, None),
        (world.globex.id, "plan_review", "success", None, 1000, 200),
    ]
    for organization_id, feature, outcome, error_type, tokens_in, tokens_out in rows:
        db.add(
            AIUsageEvent(
                organization_id=organization_id,
                user_id=world.alice.id,
                feature=feature,
                outcome=outcome,
                error_type=error_type,
                model_name="gemini-3.5-flash-lite",
                latency_ms=900,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                created_at=now - timedelta(hours=1),
            )
        )
    await db.commit()

    summary = (await world.as_staff().get("/ai-usage", params={"days": 7})).json()
    assert summary["totals"]["calls"] == 4
    assert summary["totals"]["failed"] == 1
    assert summary["totals"]["rate_limited"] == 1
    assert summary["totals"]["input_tokens"] == 2200
    acme = next(
        row for row in summary["by_organization"] if row["organization_name"] == "Acme"
    )
    assert (acme["totals"]["calls"], acme["totals"]["succeeded"]) == (3, 1)
    assert len(summary["by_day"]) == 7
    assert {row["error_type"] for row in summary["by_error_type"]} == {
        "provider_rate_limit",
        "timeout",
    }

    events = (
        await world.as_staff().get("/ai-usage/events", params={"outcome": "failed"})
    ).json()
    assert events["total"] == 1
    assert events["items"][0]["error_type"] == "timeout"
    assert events["items"][0]["organization_name"] == "Acme"


async def test_overview_counts(world):
    overview = (await world.as_staff().get("/overview")).json()
    assert overview["organizations"] == 2
    assert overview["staff"] == 1
    assert overview["plans_this_week"] == 2
    assert overview["plans_submitted_this_week"] == 2
