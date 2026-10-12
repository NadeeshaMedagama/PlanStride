"""The agents themselves, offline: prompt shape, output normalization and the
look-back tool's scoping. No model provider is ever called."""

from datetime import date, timedelta

from pydantic_ai.models.test import TestModel

from app.ai.agents import (
    KeyedTask,
    ReviewDeps,
    continues_unfinished_work,
    format_notes_for_draft,
    format_plan_for_review,
    load_previous_plans,
    plan_drafter,
    plan_reviewer,
)
from app.ai.schemas import PlanDraft, PlanReview, PreviousPlan, ReviewFinding
from app.ai.service import normalize_draft, normalize_review, unkey
from app.domain import current_week_start
from tests.factories import make_org, make_plan, make_user

MONDAY = date(2026, 10, 12)
KEYED = [
    KeyedTask(key="T1", kind="main", title="Implement checkout"),
    KeyedTask(key="T2", kind="sub_goal", title="Write tests"),
    KeyedTask(
        key="T3", kind="sub_goal", title="Webhook retries verified in staging logs"
    ),
]
EDITOR_KEYS = {"T1": "main", "T2": "sub-a", "T3": "sub-b"}
# What the look-back tool returned: last week's checkout work didn't ship.
LAST_WEEK = PreviousPlan(
    week_start=MONDAY - timedelta(weeks=1),
    status="done",
    main_task="Checkout handles expired cards, confirmed on staging",
    main_task_shipped=False,
    unfinished_tasks=[
        "Checkout handles expired cards, confirmed on staging",
        "Failed payments retry on a schedule",
    ],
    outcome_note="The refactor took longer than planned.",
)


def finding(
    task_key, category, rewrite="Checkout handles expired cards, confirmed on staging"
):
    return ReviewFinding(
        task_key=task_key,
        category=category,
        problem="Describes work, not a result you can check.",
        suggested_rewrite=rewrite,
    )


def test_plan_prompt_names_every_task_by_key_and_marks_gaps():
    prompt = format_plan_for_review(week_start=MONDAY, why_it_matters=None, tasks=KEYED)
    assert prompt == (
        "Week of Monday 12 October 2026; the plan should ship by Friday 16 October 2026.\n"
        "\n"
        "MAIN TASK\n"
        "T1: Implement checkout\n"
        "Why it matters: (not given)\n"
        "\n"
        "SUB-GOALS\n"
        "T2: Write tests\n"
        "T3: Webhook retries verified in staging logs\n"
        "\n"
        "GO-TO-MARKET GOALS\n"
        "(none)"
    )


def test_notes_prompt_fences_the_brain_dump():
    prompt = format_notes_for_draft(week_start=MONDAY, notes="finish billing page")
    assert "<notes>\nfinish billing page\n</notes>" in prompt


def test_normalize_review_keeps_actionable_findings_tied_to_real_tasks():
    review = PlanReview(
        verdict="needs_work",
        summary='  "Implement checkout" is an activity, not a result.  ',
        findings=[
            finding("t1", "not_verifiable"),  # lower-case key still resolves
            finding("T2", "not_verifiable", rewrite='"Tests cover the retry schedule"'),
            finding(None, "missing_why", rewrite="Expired cards cost us renewals."),
            finding(
                "T2", "missing_go_to_market", rewrite="Changelog entry for checkout."
            ),
            finding("T9", "not_verifiable"),  # invented key: dropped
            finding("T1", "not_verifiable", rewrite="Something else"),  # duplicate
            finding(
                "T3",
                "not_verifiable",
                rewrite="Webhook retries verified in staging logs",
            ),
        ],
    )

    result = normalize_review(review, KEYED, EDITOR_KEYS)

    assert result.verdict == "needs_work"
    # Whitespace collapsed; a quoted phrase inside the text survives intact.
    assert result.summary == '"Implement checkout" is an activity, not a result.'

    assert [(f.task_key, f.category, f.action) for f in result.findings] == [
        ("main", "not_verifiable", "replace_title"),
        ("sub-a", "not_verifiable", "replace_title"),
        ("main", "missing_why", "set_why"),
        (None, "missing_go_to_market", "add_go_to_market"),
    ]
    # Quotes wrapped around a rewrite are dropped; task titles lose a trailing
    # period; the why sentence keeps its own.
    assert result.findings[1].suggested_rewrite == "Tests cover the retry schedule"
    assert result.findings[2].suggested_rewrite == "Expired cards cost us renewals."
    assert result.findings[3].suggested_rewrite == "Changelog entry for checkout"


def test_normalize_review_points_scope_findings_at_the_main_task():
    review = PlanReview(
        verdict="needs_work",
        summary="Too big.",
        findings=[finding(None, "scope_too_big", rewrite="Card retries live for EU")],
    )
    result = normalize_review(review, KEYED, EDITOR_KEYS)
    assert result.findings[0].task_key == "main"


def test_normalize_review_keeps_one_rewrite_per_task_the_most_specific():
    review = PlanReview(
        verdict="needs_work",
        summary="Last week's work again.",
        findings=[
            finding("T1", "not_verifiable", rewrite="Checkout works on staging"),
            finding("T1", "missing_why", rewrite="Expired cards cost us renewals."),
            finding("T2", "scope_too_big", rewrite="Retry tests pass in CI"),
            finding("T1", "carry_over", rewrite="Expired-card retries live on staging"),
            finding("T2", "not_verifiable", rewrite="Tests written"),
        ],
    )

    result = normalize_review(review, KEYED, EDITOR_KEYS, [LAST_WEEK])

    # The carry-over replaces the vaguer finding about the same title, in its
    # place; the reason is a separate suggestion and stays.
    assert [(f.task_key, f.category) for f in result.findings] == [
        ("main", "carry_over"),
        ("main", "missing_why"),
        ("sub-a", "scope_too_big"),
    ]
    assert (
        result.findings[0].suggested_rewrite == "Expired-card retries live on staging"
    )


def test_carry_over_must_be_backed_by_unfinished_work_the_tool_returned():
    review = PlanReview(
        verdict="needs_work",
        summary="Carried over.",
        findings=[
            # "checkout" was left unfinished last week: a real carry-over.
            finding(
                "T1", "carry_over", rewrite="Expired-card checkout live on staging"
            ),
            # "retries" matches last week's unfinished "retry" work.
            finding("T3", "carry_over", rewrite="Webhook retries replay cleanly"),
            # Nothing unfinished was about tests: the model is guessing.
            finding("T2", "carry_over", rewrite="Checkout tests pass in CI"),
        ],
    )

    result = normalize_review(review, KEYED, EDITOR_KEYS, [LAST_WEEK])
    assert [f.task_key for f in result.findings] == ["main", "sub-b"]

    # Without a look-back (the model never called the tool, or the member has
    # no earlier plans) no carry-over can be backed up.
    assert normalize_review(review, KEYED, EDITOR_KEYS).findings == []


def test_continues_unfinished_work_compares_topics_not_filler():
    history = [
        PreviousPlan(
            week_start=MONDAY - timedelta(weeks=1),
            status="approved",
            main_task="Access logs kept for every request",
            main_task_shipped=None,
            unfinished_tasks=["Access logs kept for every request", "Rate limits live"],
            outcome_note=None,
        )
    ]
    assert continues_unfinished_work("Access log retention verified", history)
    assert continues_unfinished_work("Rate limiting enforced on staging", history)
    # Sharing only "live", "verified" or "staging" says nothing about the work.
    assert not continues_unfinished_work("Postgres upgrade live on staging", history)


def test_normalize_review_never_suggests_a_duplicate_task():
    review = PlanReview(
        verdict="needs_work",
        summary="Tighten it up.",
        findings=[
            # Renaming a task to another task's title.
            finding("T1", "not_verifiable", rewrite="write tests"),
            finding("T2", "not_verifiable", rewrite="Checkout tests pass in CI"),
            # The same text as an earlier suggestion.
            finding("T3", "not_verifiable", rewrite="Checkout tests pass in CI"),
            # A go-to-market goal the plan already has, as a sub-goal or not.
            finding(None, "missing_go_to_market", rewrite="Write tests."),
            # Nothing to apply at all.
            finding("T3", "scope_too_big", rewrite="  "),
        ],
    )
    result = normalize_review(review, KEYED, EDITOR_KEYS)
    assert [(f.task_key, f.suggested_rewrite) for f in result.findings] == [
        ("sub-a", "Checkout tests pass in CI")
    ]


def test_unkey_puts_leaked_task_keys_back_into_words():
    keyed = [*KEYED, KeyedTask(key="T4", kind="go_to_market", title="Changelog entry")]

    def own(text, key):
        return unkey(text, keyed, own_key=key)

    assert own("Task T1 is an activity, not a result.", "T1") == (
        "The main task is an activity, not a result."
    )
    assert own("T2 says what you'll do, not what will be true.", "T2") == (
        "This sub-goal says what you'll do, not what will be true."
    )
    assert own("Nobody will hear about T4 yet.", "T4") == (
        "Nobody will hear about this go-to-market goal yet."
    )
    # Right before the task's own words, the key just goes.
    assert own("T2 'Write tests' describes activity.", "T2") == (
        "'Write tests' describes activity."
    )
    assert own("T1: Implement checkout is work to do.", "T1") == (
        "Implement checkout is work to do."
    )
    assert own("The main task (T1) has no reason.", "T1") == (
        "The main task has no reason."
    )
    # Other tasks are named by their words; ranges become "the tasks", even
    # when the model miscounts.
    assert unkey("Rewrite T1-T3 as results; T2 is the vaguest.", keyed) == (
        "Rewrite the tasks as results; “Write tests” is the vaguest."
    )
    assert unkey("T1 to T9 need work.", keyed) == "The tasks need work."
    assert unkey("T7–T9 are fine.", keyed) == "T7–T9 are fine."
    assert unkey("T2 and T3 overlap.", keyed) == (
        "“Write tests” and “Webhook retries verified in staging logs” overlap."
    )
    # Keys the plan doesn't have, and keys that are part of a real title, stay.
    assert unkey("T9 is not a task here.", keyed) == "T9 is not a task here."
    instances = [
        KeyedTask(key="T1", kind="main", title="Move workers to T3 instances"),
        KeyedTask(key="T2", kind="sub_goal", title="Drain the old pool"),
        KeyedTask(key="T3", kind="sub_goal", title="Dashboards updated"),
    ]
    assert unkey("Moving to T3 needs a check; T2 too.", instances) == (
        "Moving to T3 needs a check; “Drain the old pool” too."
    )


def test_normalize_review_never_shows_keys_to_the_member():
    review = PlanReview(
        verdict="needs_work",
        summary="T1 carries over and T2 is an activity.",
        findings=[
            ReviewFinding(
                task_key="T2",
                category="not_verifiable",
                problem="T2 describes activity instead of a result.",
                suggested_rewrite="Retry schedule covered by tests, passing in CI",
            )
        ],
    )
    result = normalize_review(review, KEYED, EDITOR_KEYS)
    assert result.summary == (
        "“Implement checkout” carries over and “Write tests” is an activity."
    )
    assert result.findings[0].problem == (
        "This sub-goal describes activity instead of a result."
    )


def test_normalize_review_caps_findings_at_six():
    tasks = [
        KeyedTask(key=f"T{i}", kind="sub_goal", title=f"Do thing {i}")
        for i in range(1, 10)
    ]
    tasks[0] = KeyedTask(key="T1", kind="main", title="Do thing 1")
    review = PlanReview(
        verdict="needs_work",
        summary="Lots.",
        findings=[
            finding(task.key, "not_verifiable", rewrite=f"Thing {task.key} done")
            for task in tasks
        ],
    )
    result = normalize_review(review, tasks, {task.key: task.key for task in tasks})
    assert len(result.findings) == 6


def test_normalize_draft_trims_to_what_the_form_holds():
    draft = PlanDraft(
        main_task="  Billing page live for all workspaces.  ",
        why_it_matters="Customers can't upgrade without it.",
        sub_goals=[
            "Plan picker works",
            "plan picker works",
            "",
            *[f"Goal {i}" for i in range(10)],
        ],
        go_to_market=["Changelog entry."],
        left_out=["Dentist on Tuesday"],
        open_questions=[
            "Annual plans too?",
            "Which currency?",
            "Who signs off?",
            "Extra?",
        ],
    )
    clean = normalize_draft(draft)
    assert clean.main_task == "Billing page live for all workspaces"
    assert clean.sub_goals[0] == "Plan picker works"
    assert len(clean.sub_goals) == 8  # deduped, blank dropped, capped
    assert clean.go_to_market == ["Changelog entry"]
    assert len(clean.open_questions) == 3


async def test_agents_return_typed_output_with_test_model(db):
    owner = await make_user(db)
    organization = await make_org(db, "Acme", owner=owner)
    deps = ReviewDeps(
        session=db,
        organization_id=organization.id,
        user_id=owner.id,
        week_start=current_week_start(),
        task_titles={"T1": "Implement checkout"},
    )
    model = TestModel()
    review = await plan_reviewer.run("plan", deps=deps, model=model)
    assert isinstance(review.output, PlanReview)
    # TestModel calls every tool, so the look-back tool ran against the DB,
    # and what it returned is kept for checking carry-overs.
    assert model.last_model_request_parameters is not None
    assert [
        tool.name for tool in model.last_model_request_parameters.function_tools
    ] == ["previous_plans"]
    assert deps.looked_back == []  # this owner has no earlier plans

    draft = await plan_drafter.run("notes", model=TestModel())
    assert isinstance(draft.output, PlanDraft)


async def test_look_back_reads_only_this_members_earlier_plans(db):
    alice, bob = await make_user(db, "Alice"), await make_user(db, "Bob")
    acme = await make_org(db, "Acme", owner=alice)
    other = await make_org(db, "Other", owner=alice)
    this_week = current_week_start()

    for weeks_ago, title in ((1, "Last week"), (2, "Two weeks ago"), (3, "Too old")):
        await make_plan(
            db,
            acme,
            alice,
            week_start=this_week - timedelta(weeks=weeks_ago),
            status="done",
            main_task=title,
            main_task_shipped=weeks_ago != 1,
            outcome_note="The refactor took longer than planned."
            if weeks_ago == 1
            else None,
        )
    await make_plan(db, acme, alice, week_start=this_week, main_task="This week")
    await make_plan(
        db,
        other,
        alice,
        week_start=this_week - timedelta(weeks=1),
        main_task="Other org",
    )
    await make_plan(
        db, acme, bob, week_start=this_week - timedelta(weeks=1), main_task="Bob's"
    )

    previous = await load_previous_plans(
        db, organization_id=acme.id, user_id=alice.id, before=this_week
    )

    assert [plan.main_task for plan in previous] == ["Last week", "Two weeks ago"]
    assert previous[0].unfinished_tasks  # nothing was ticked in these fixtures
    # What the reviewer needs to call a carry-over, in the member's own words.
    assert previous[0].main_task_shipped is False
    assert previous[0].outcome_note == "The refactor took longer than planned."
    assert previous[1].main_task_shipped is True
