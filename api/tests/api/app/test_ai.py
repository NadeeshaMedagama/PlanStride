"""The AI endpoints, offline. Models are Pydantic AI's FunctionModel/TestModel;
`ALLOW_MODEL_REQUESTS = False` (conftest) makes any real provider call fail."""

import asyncio
from datetime import timedelta

import pytest
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select

from app.config import settings
from app.domain import current_week_start
from app.models import AIUsageEvent, WeeklyPlan
from tests.factories import error_code, make_plan

THIS_WEEK = current_week_start()

REVIEW_BODY = {
    "week_start": THIS_WEEK.isoformat(),
    "why_it_matters": None,
    "tasks": [
        {"key": "main-x", "kind": "main", "title": "Implement checkout"},
        {"key": "sub-1", "kind": "sub_goal", "title": "Write tests"},
    ],
}
DRAFT_BODY = {
    "week_start": THIS_WEEK.isoformat(),
    "notes": "need to finish the billing page, probably also fix that webhook bug, "
    "should announce it in the changelog",
}


def returning(output: dict, calls: list | None = None) -> FunctionModel:
    """A model that answers every run with `output` via the output tool."""

    def respond(messages, info: AgentInfo) -> ModelResponse:
        if calls is not None:
            calls.append(messages)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    return FunctionModel(respond)


def raising(error: Exception) -> FunctionModel:
    def respond(messages, info):
        raise error

    return FunctionModel(respond)


async def events(db):
    result = await db.scalars(select(AIUsageEvent).order_by(AIUsageEvent.created_at))
    return result.all()


def review_url(world, organization=None):
    return f"/organizations/{(organization or world.acme).id}/ai/plan-review"


def draft_url(world):
    return f"/organizations/{world.acme.id}/ai/plan-draft"


# --- Plan review -------------------------------------------------------------------------


async def test_review_returns_findings_tied_to_editor_tasks(world, db, use_model):
    calls: list = []
    use_model(
        returning(
            {
                "verdict": "needs_work",
                "summary": "Both tasks describe work. Say what will be true by Friday.",
                "findings": [
                    {
                        "task_key": "T1",
                        "category": "not_verifiable",
                        "problem": '"Implement checkout" is work to do, not a result.',
                        "suggested_rewrite": "Checkout handles expired cards, confirmed on staging",
                    },
                    {
                        "task_key": "T1",
                        "category": "missing_why",
                        "problem": "The main task doesn't say why it matters.",
                        "suggested_rewrite": "Failed card payments are our top churn reason.",
                    },
                    {
                        "task_key": None,
                        "category": "missing_go_to_market",
                        "problem": "Nothing puts the checkout fix in front of users.",
                        "suggested_rewrite": "Changelog entry announcing card retries",
                    },
                    {
                        "task_key": "T7",
                        "category": "not_verifiable",
                        "problem": "Invented task.",
                        "suggested_rewrite": "Should never reach the UI",
                    },
                ],
            },
            calls,
        )
    )

    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "needs_work"
    assert [(f["task_key"], f["action"]) for f in body["findings"]] == [
        ("main-x", "replace_title"),
        ("main-x", "set_why"),
        (None, "add_go_to_market"),
    ]

    # The model saw the plan with short keys and the gaps called out.
    prompt = next(
        part.content
        for message in calls[0]
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart)
    )
    assert "T1: Implement checkout" in prompt
    assert "T2: Write tests" in prompt
    assert "Why it matters: (not given)" in prompt

    [event] = await events(db)
    assert event.organization_id == world.acme.id
    assert event.user_id == world.alice.id
    assert (event.feature, event.outcome, event.error_type) == (
        "plan_review",
        "success",
        None,
    )
    assert event.input_tokens is not None and event.output_tokens is not None
    assert event.latency_ms is not None


async def test_review_looks_back_at_the_members_own_previous_plans(
    world, db, use_model
):
    last_week = THIS_WEEK - timedelta(weeks=1)
    await make_plan(
        db,
        world.acme,
        world.alice,
        week_start=last_week,
        status="done",
        main_task="Checkout handles expired cards, confirmed on staging",
        main_task_shipped=False,
        outcome_note="The card network's sandbox was down on Wednesday.",
    )
    # Someone else's history must never reach the model.
    await make_plan(
        db, world.acme, world.bob, week_start=last_week, main_task="Bob secret"
    )
    await make_plan(
        db, world.globex, world.carol, week_start=last_week, main_task="Carol secret"
    )

    seen: dict = {}

    def respond(messages, info: AgentInfo) -> ModelResponse:
        returns = [
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("previous_plans", {})])
        seen["history"] = returns[0].model_response_str()
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {
                        "verdict": "needs_work",
                        "summary": "This is last week's checkout work again.",
                        "findings": [
                            {
                                "task_key": "T1",
                                "category": "carry_over",
                                "problem": "Carried over from last week unfinished.",
                                "suggested_rewrite": "Expired-card retry ships for EU cards only",
                            }
                        ],
                    },
                )
            ]
        )

    use_model(FunctionModel(respond))
    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)

    assert response.status_code == 200, response.text
    assert response.json()["findings"][0]["category"] == "carry_over"
    assert "Checkout handles expired cards" in seen["history"]
    assert "sandbox was down" in seen["history"]  # the member's own note
    assert "Bob secret" not in seen["history"]
    assert "Carol secret" not in seen["history"]


CARRY_OVER = {
    "task_key": "T1",
    "category": "carry_over",
    "problem": "This is last week's work again.",
    "suggested_rewrite": "Checkout ships for EU cards only",
}
GO_TO_MARKET = {
    "task_key": None,
    "category": "missing_go_to_market",
    "problem": "Nothing puts the work in front of users.",
    "suggested_rewrite": "Changelog entry for the checkout fix",
}


def looking_back(answer) -> tuple[FunctionModel, list[str]]:
    """A model that calls the look-back tool, then answers with
    `answer(retry_messages)`; also returns the retry messages it was sent."""
    retries: list[str] = []

    def respond(messages, info: AgentInfo) -> ModelResponse:
        parts = [
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
        ]
        if not any(isinstance(part, ToolReturnPart) for part in parts):
            return ModelResponse(parts=[ToolCallPart("previous_plans", {})])
        retries[:] = [
            part.model_response() for part in parts if isinstance(part, RetryPromptPart)
        ]
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, answer(retries))]
        )

    return FunctionModel(respond), retries


async def test_unbacked_carry_over_goes_back_to_the_model(world, db, use_model):
    # Last week's unfinished work had nothing to do with checkout.
    await make_plan(
        db,
        world.acme,
        world.alice,
        week_start=THIS_WEEK - timedelta(weeks=1),
        status="done",
        main_task="Refunds reach the ledger within a minute",
        main_task_shipped=False,
    )
    model, retries = looking_back(
        lambda retries: {
            "verdict": "needs_work",
            "summary": "Say what will be true by Friday.",
            "findings": [GO_TO_MARKET] if retries else [CARRY_OVER, GO_TO_MARKET],
        }
    )
    use_model(model)

    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)

    assert response.status_code == 200, response.text
    assert [f["category"] for f in response.json()["findings"]] == [
        "missing_go_to_market"
    ]
    # The model was told which task isn't a carry-over, and answered again.
    [retry] = retries
    assert '"Implement checkout"' in retry
    [event] = await events(db)
    assert event.outcome == "success"


async def test_a_model_that_insists_still_never_shows_an_unbacked_carry_over(
    world, db, use_model
):
    model, retries = looking_back(
        lambda retries: {
            "verdict": "needs_work",
            "summary": "Carried over.",
            "findings": [CARRY_OVER, GO_TO_MARKET],
        }
    )
    use_model(model)

    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)

    # Out of retries, the review still arrives, without the made-up finding.
    assert response.status_code == 200, response.text
    assert [f["category"] for f in response.json()["findings"]] == [
        "missing_go_to_market"
    ]
    assert len(retries) == 2


async def test_review_never_changes_the_saved_plan(world, db, use_model):
    use_model(returning({"verdict": "ready", "summary": "Ship it.", "findings": []}))
    before = (
        await world.as_(world.alice).get(
            f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}"
        )
    ).json()

    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)
    assert response.json() == {
        "verdict": "ready",
        "summary": "Ship it.",
        "findings": [],
    }

    after = (
        await world.as_(world.alice).get(
            f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}"
        )
    ).json()
    assert after == before


async def test_review_request_must_have_exactly_one_main_task(world, db, use_model):
    use_model(returning({"verdict": "ready", "summary": "", "findings": []}))
    no_main = {**REVIEW_BODY, "tasks": [{"key": "a", "kind": "sub_goal", "title": "x"}]}
    duplicate_keys = {
        **REVIEW_BODY,
        "tasks": [
            {"key": "a", "kind": "main", "title": "x"},
            {"key": "a", "kind": "sub_goal", "title": "y"},
        ],
    }
    for body in (no_main, duplicate_keys):
        response = await world.as_(world.alice).post(review_url(world), json=body)
        assert response.status_code == 422
    assert await events(db) == []  # rejected before any AI call


# --- Draft from a brain dump ------------------------------------------------------------------


async def test_draft_returns_a_plan_for_the_form_and_saves_nothing(
    world, db, use_model
):
    use_model(
        returning(
            {
                "main_task": "Billing page live for all workspaces, verified in production.",
                "why_it_matters": "Customers can't upgrade plans without it.",
                "sub_goals": [
                    "Webhook retries no longer drop payment events",
                    "Webhook retries no longer drop payment events",
                ],
                "go_to_market": ["Changelog entry announcing the billing page"],
                "left_out": [],
                "open_questions": ["Does the billing page include annual plans?"],
            }
        )
    )
    plans_before = await db.scalar(select(func.count()).select_from(WeeklyPlan))

    response = await world.as_(world.bob).post(draft_url(world), json=DRAFT_BODY)

    assert response.status_code == 200, response.text
    draft = response.json()
    assert (
        draft["main_task"]
        == "Billing page live for all workspaces, verified in production"
    )
    assert draft["sub_goals"] == ["Webhook retries no longer drop payment events"]
    assert draft["go_to_market"] == ["Changelog entry announcing the billing page"]
    assert await db.scalar(select(func.count()).select_from(WeeklyPlan)) == plans_before
    [event] = await events(db)
    assert (event.feature, event.outcome) == ("plan_draft", "success")


async def test_draft_validates_notes(world, db, use_model):
    use_model(returning({}))
    response = await world.as_(world.bob).post(
        draft_url(world), json={**DRAFT_BODY, "notes": "too short"}
    )
    assert response.status_code == 422
    too_long = await world.as_(world.bob).post(
        draft_url(world), json={**DRAFT_BODY, "notes": "x" * 4001}
    )
    assert too_long.status_code == 422


# --- Failure handling: the product works without the AI -----------------------------------------


@pytest.mark.parametrize(
    ("model", "status", "code", "outcome", "error_type"),
    [
        (None, 503, "ai_not_configured", "failed", "not_configured"),
        (
            raising(
                ModelHTTPError(
                    status_code=429, model_name="gemini", body={"error": "quota"}
                )
            ),
            429,
            "ai_rate_limited",
            "rate_limited",
            "provider_rate_limit",
        ),
        (
            raising(
                ModelHTTPError(
                    status_code=503, model_name="gemini", body={"error": "down"}
                )
            ),
            503,
            "ai_unavailable",
            "failed",
            "provider_error",
        ),
        (
            returning({"verdict": "maybe", "summary": "?", "findings": "lots"}),
            502,
            "ai_invalid_output",
            "failed",
            "invalid_output",
        ),
    ],
    ids=["no-key", "rate-limited", "provider-down", "invalid-output"],
)
async def test_ai_failures_become_plain_messages_and_are_recorded(
    world, db, use_model, model, status, code, outcome, error_type
):
    use_model(model)
    for url, body in ((review_url(world), REVIEW_BODY), (draft_url(world), DRAFT_BODY)):
        response = await world.as_(world.alice).post(url, json=body)
        assert response.status_code == status
        assert error_code(response) == code
        message = response.json()["detail"][0]["msg"]
        assert "Traceback" not in message and "gemini" not in message.lower()

    recorded = await events(db)
    assert [(e.feature, e.outcome, e.error_type) for e in recorded] == [
        ("plan_review", outcome, error_type),
        ("plan_draft", outcome, error_type),
    ]
    assert all(e.organization_id == world.acme.id for e in recorded)

    # Planning carries on regardless.
    submit = await world.as_(world.alice).post(
        f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}/withdraw"
    )
    assert submit.status_code == 200


async def test_slow_model_times_out_instead_of_hanging(
    world, db, use_model, monkeypatch
):
    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 0.2)

    async def slow(messages, info):
        await asyncio.sleep(5)
        raise AssertionError("should have been cancelled")

    use_model(FunctionModel(slow))
    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)

    assert response.status_code == 504
    assert error_code(response) == "ai_timeout"
    [event] = await events(db)
    assert (event.outcome, event.error_type) == ("failed", "timeout")


async def test_per_user_throttle_protects_the_shared_quota(
    world, db, use_model, monkeypatch
):
    monkeypatch.setattr(settings, "AI_REQUESTS_PER_USER_PER_MINUTE", 2)
    calls: list = []
    use_model(
        returning({"verdict": "ready", "summary": "Fine.", "findings": []}, calls)
    )
    alice = world.as_(world.alice)

    statuses = [
        (await alice.post(review_url(world), json=REVIEW_BODY)).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
    assert len(calls) == 2  # the throttled request never reached the model

    # Throttling is per user: a colleague is unaffected.
    assert (
        await world.as_(world.lead).post(review_url(world), json=REVIEW_BODY)
    ).status_code == 200
    throttled = [e for e in await events(db) if e.error_type == "throttled"]
    assert len(throttled) == 1 and throttled[0].outcome == "rate_limited"


async def test_usage_is_recorded_against_the_calling_organization(world, db, use_model):
    use_model(returning({"verdict": "ready", "summary": "Fine.", "findings": []}))
    await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)
    await world.as_(world.carol).post(review_url(world, world.globex), json=REVIEW_BODY)
    # Calling into an organization you're not in is refused before any AI call.
    refused = await world.as_(world.carol).post(review_url(world), json=REVIEW_BODY)
    assert refused.status_code == 404

    recorded = await events(db)
    assert sorted(str(e.organization_id) for e in recorded) == sorted(
        [str(world.acme.id), str(world.globex.id)]
    )


async def test_the_api_key_never_reaches_a_response(world, use_model, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "sk-very-secret-key")
    use_model(
        raising(ModelHTTPError(status_code=400, model_name="gemini", body={"key": "x"}))
    )
    response = await world.as_(world.alice).post(review_url(world), json=REVIEW_BODY)
    assert "sk-very-secret-key" not in response.text
