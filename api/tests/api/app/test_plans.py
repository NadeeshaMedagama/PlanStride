from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain import current_week_start
from app.models import PlanTask, WeeklyPlan
from tests.factories import error_code, make_plan, plan_body

THIS_WEEK = current_week_start()
NEXT_WEEK = THIS_WEEK + timedelta(weeks=1)


def plans_url(world, suffix=""):
    return f"/organizations/{world.acme.id}/plans{suffix}"


def plan_url(world, plan, suffix=""):
    return plans_url(world, f"/{plan.id}{suffix}")


async def create(world, user, **overrides):
    body = {**plan_body(), "week_start": NEXT_WEEK.isoformat(), **overrides}
    return await world.as_(user).post(plans_url(world), json=body)


# --- Creating and editing ---------------------------------------------------------------


async def test_member_creates_a_structured_draft(world):
    response = await create(world, world.bob)

    assert response.status_code == 201
    plan = response.json()
    assert plan["status"] == "draft"
    assert [task["kind"] for task in plan["tasks"]] == [
        "main",
        "sub_goal",
        "go_to_market",
    ]
    assert all(task["status"] == "todo" for task in plan["tasks"])
    assert plan["permissions"]["can_edit"] and plan["permissions"]["can_submit"]
    assert not plan["permissions"]["can_review"]


async def test_plans_are_keyed_by_monday(world):
    tuesday = NEXT_WEEK + timedelta(days=1)
    response = await create(world, world.bob, week_start=tuesday.isoformat())
    assert response.status_code == 400
    assert response.json()["detail"][0]["loc"] == ["body", "week_start"]


async def test_planning_window_is_last_week_to_four_weeks_ahead(world):
    too_old = await create(
        world, world.bob, week_start=(THIS_WEEK - timedelta(weeks=3)).isoformat()
    )
    too_far = await create(
        world, world.bob, week_start=(THIS_WEEK + timedelta(weeks=8)).isoformat()
    )
    assert too_old.status_code == 400
    assert too_far.status_code == 400


async def test_one_plan_per_member_per_week(world):
    assert (await create(world, world.bob)).status_code == 201
    duplicate = await create(world, world.bob)
    assert duplicate.status_code == 409


async def test_main_task_is_required_and_lists_are_capped(world):
    no_main = await create(world, world.bob, main_task="   ")
    too_many = await create(
        world, world.bob, sub_goals=[{"title": f"Goal {i}"} for i in range(9)]
    )
    assert no_main.status_code == 422
    assert too_many.status_code == 422


async def test_editing_keeps_ticked_tasks_and_replaces_the_rest(world):
    created = (await create(world, world.bob)).json()
    sub = next(task for task in created["tasks"] if task["kind"] == "sub_goal")
    actor = world.as_(world.bob)
    await actor.patch(
        plans_url(world, f"/{created['id']}/tasks/{sub['id']}"), json={"status": "done"}
    )

    response = await actor.put(
        plans_url(world, f"/{created['id']}"),
        json=plan_body(
            main_task="Refunds reach the ledger within a minute, verified in production",
            sub_goals=[
                {"id": sub["id"], "title": "Partial refunds in the dialog"},
                {"title": "Refund webhook covered by tests"},
            ],
            go_to_market=[],
        ),
    )

    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert [task["kind"] for task in tasks] == ["main", "sub_goal", "sub_goal"]
    kept = next(task for task in tasks if task["id"] == sub["id"])
    assert kept["status"] == "done" and kept["title"] == "Partial refunds in the dialog"


async def test_editing_rejects_tasks_from_another_plan(world, db):
    created = (await create(world, world.bob)).json()
    foreign_task = await db.scalar(
        select(PlanTask.id).where(
            PlanTask.plan_id == world.alice_plan.id, PlanTask.kind == "sub_goal"
        )
    )
    response = await world.as_(world.bob).put(
        plans_url(world, f"/{created['id']}"),
        json=plan_body(sub_goals=[{"id": str(foreign_task), "title": "Mine now"}]),
    )
    assert response.status_code == 400


async def test_only_drafts_can_be_edited_or_deleted(world):
    actor = world.as_(world.alice)  # alice's plan is submitted
    edit = await actor.put(plan_url(world, world.alice_plan), json=plan_body())
    delete = await actor.delete(plan_url(world, world.alice_plan))
    assert edit.status_code == 409 and error_code(edit) == "invalid_state"
    assert delete.status_code == 409


async def test_author_deletes_own_draft(world, db):
    created = (await create(world, world.bob)).json()
    response = await world.as_(world.bob).delete(plans_url(world, f"/{created['id']}"))
    assert response.status_code == 204
    assert await db.get(WeeklyPlan, created["id"]) is None


async def test_nobody_edits_someone_elses_plan(world):
    for user in (world.lead, world.owner, world.admin):
        response = await world.as_(user).put(
            plan_url(world, world.alice_plan), json=plan_body()
        )
        assert response.status_code == 403


# --- Lifecycle: draft -> submitted -> approved -> done ----------------------------------------


async def test_full_week_lifecycle(world):
    created = (await create(world, world.alice)).json()
    plan_id = created["id"]
    alice, lead = world.as_(world.alice), world.as_(world.lead)

    submitted = await alice.post(plans_url(world, f"/{plan_id}/submit"))
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["permissions"]["can_withdraw"]

    approved = await lead.post(
        plans_url(world, f"/{plan_id}/approve"), json={"comment": "Go"}
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["review_decision"] == "approved"
    assert body["reviewed_by"]["id"] == str(world.lead.id)

    for task in body["tasks"][1:]:
        ticked = await alice.patch(
            plans_url(world, f"/{plan_id}/tasks/{task['id']}"), json={"status": "done"}
        )
        assert ticked.status_code == 200

    done = await alice.post(
        plans_url(world, f"/{plan_id}/complete"),
        json={"main_task_shipped": True, "outcome_note": "Shipped Thursday"},
    )
    assert done.status_code == 200
    final = done.json()
    assert final["status"] == "done"
    assert final["main_task_shipped"] is True
    assert final["tasks_done"] == final["tasks_total"]  # shipping ticks the main task
    assert not any(final["permissions"].values())

    frozen = await alice.patch(
        plans_url(world, f"/{plan_id}/tasks/{final['tasks'][0]['id']}"),
        json={"status": "todo"},
    )
    assert frozen.status_code == 409


async def test_unshipped_week_keeps_main_task_open(world):
    plan = await approved_alice_plan(world)
    done = await world.as_(world.alice).post(
        plan_url(world, plan, "/complete"),
        json={"main_task_shipped": False, "outcome_note": "Blocked by the vendor"},
    )
    body = done.json()
    assert body["main_task_shipped"] is False
    assert body["outcome_note"] == "Blocked by the vendor"
    assert body["tasks"][0]["status"] == "todo"


async def approved_alice_plan(world):
    """Alice's submitted plan, approved by her lead."""
    await world.as_(world.lead).post(
        plan_url(world, world.alice_plan, "/approve"), json={}
    )
    return world.alice_plan


async def test_return_sends_plan_back_to_draft_with_comment(world):
    response = await world.as_(world.lead).post(
        plan_url(world, world.alice_plan, "/return"),
        json={"comment": "Main task is two projects. Pick one."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["review_decision"] == "returned"
    assert body["review_comment"] == "Main task is two projects. Pick one."

    # The author sees the comment and can edit and resubmit.
    mine = await world.as_(world.alice).get(plan_url(world, world.alice_plan))
    assert mine.json()["review_comment"] == "Main task is two projects. Pick one."
    assert mine.json()["permissions"]["can_edit"]
    resubmit = await world.as_(world.alice).post(
        plan_url(world, world.alice_plan, "/submit")
    )
    assert resubmit.json()["status"] == "submitted"


async def test_return_requires_a_comment(world):
    response = await world.as_(world.lead).post(
        plan_url(world, world.alice_plan, "/return"), json={"comment": ""}
    )
    assert response.status_code == 422


async def test_withdraw_before_review(world):
    response = await world.as_(world.alice).post(
        plan_url(world, world.alice_plan, "/withdraw")
    )
    assert response.json()["status"] == "draft"


async def test_invalid_transitions_are_refused(world):
    alice, lead = world.as_(world.alice), world.as_(world.lead)
    assert (
        await alice.post(plan_url(world, world.alice_plan, "/submit"))
    ).status_code == 409
    assert (
        await alice.post(
            plan_url(world, world.alice_plan, "/complete"),
            json={"main_task_shipped": True},
        )
    ).status_code == 409
    await lead.post(plan_url(world, world.alice_plan, "/approve"), json={})
    assert (
        await lead.post(plan_url(world, world.alice_plan, "/approve"), json={})
    ).status_code == 409
    assert (
        await alice.post(plan_url(world, world.alice_plan, "/withdraw"))
    ).status_code == 409


# --- Who may approve ------------------------------------------------------------------------


async def test_only_the_authors_team_lead_can_review(world):
    url = plan_url(world, world.alice_plan, "/approve")
    teammate = await world.as_(world.beta_lead).post(
        url, json={}
    )  # on Alpha, leads Beta
    admin = await world.as_(world.admin).post(url, json={})
    owner = await world.as_(world.owner).post(url, json={})

    assert teammate.status_code == 403 and error_code(teammate) == "team_lead_required"
    assert admin.status_code == 403 and error_code(admin) == "team_lead_required"
    assert owner.status_code == 403
    # A lead of an unrelated team can't even see the plan.
    unrelated = await world.as_(world.bob).post(url, json={})
    assert unrelated.status_code == 404

    lead = await world.as_(world.lead).post(url, json={})
    assert lead.status_code == 200


async def test_lead_on_two_teams_is_reviewed_by_the_other_lead(world, db):
    # Bianca leads Beta and is a member of Alpha: Leah (Alpha's lead) reviews her.
    plan = await make_plan(db, world.acme, world.beta_lead, status="submitted")
    url = plan_url(world, plan, "/approve")

    # Bob is on Beta with her, so he can see the plan, but she leads Beta:
    # being on a team with the author isn't enough to approve.
    teammate = await world.as_(world.bob).post(url, json={})
    assert teammate.status_code == 403
    approved = await world.as_(world.lead).post(url, json={})
    assert approved.status_code == 200

    # And Bianca reviews Bob, from the team she leads.
    bob_plan = await make_plan(db, world.acme, world.bob, status="submitted")
    assert (
        await world.as_(world.beta_lead).post(
            plan_url(world, bob_plan, "/approve"), json={}
        )
    ).status_code == 200


async def test_leads_cannot_review_their_own_plan(world, db):
    plan = await make_plan(db, world.acme, world.lead, status="submitted")
    response = await world.as_(world.lead).post(
        plan_url(world, plan, "/approve"), json={}
    )
    assert response.status_code == 403
    assert error_code(response) == "self_review"


async def test_lead_removed_from_team_loses_review_rights(world):
    await world.as_(world.owner).delete(
        f"/organizations/{world.acme.id}/teams/{world.alpha.id}/members/{world.lead.id}"
    )
    response = await world.as_(world.lead).post(
        plan_url(world, world.alice_plan, "/approve"), json={}
    )
    assert response.status_code in (403, 404)


async def test_my_week_names_who_can_approve(world):
    response = await world.as_(world.alice).get(
        f"/organizations/{world.acme.id}/me/weeks/{THIS_WEEK.isoformat()}"
    )
    body = response.json()
    assert body["plan"]["id"] == str(world.alice_plan.id)
    assert [reviewer["id"] for reviewer in body["reviewers"]] == [str(world.lead.id)]

    nobody = await world.as_(world.owner).get(
        f"/organizations/{world.acme.id}/me/weeks/{THIS_WEEK.isoformat()}"
    )
    assert nobody.json() == {
        "week_start": THIS_WEEK.isoformat(),
        "plan": None,
        "reviewers": [],
    }


async def test_review_queue_lists_submitted_plans_from_led_teams(world, db):
    await make_plan(db, world.acme, world.bob, status="submitted")
    await make_plan(db, world.acme, world.beta_lead, status="draft")

    leah = (
        await world.as_(world.lead).get(f"/organizations/{world.acme.id}/reviews")
    ).json()
    bianca = (
        await world.as_(world.beta_lead).get(f"/organizations/{world.acme.id}/reviews")
    ).json()
    alice = (
        await world.as_(world.alice).get(f"/organizations/{world.acme.id}/reviews")
    ).json()

    assert [item["plan"]["author"]["first_name"] for item in leah] == ["Alice"]
    assert [team["name"] for team in leah[0]["teams"]] == ["Alpha"]
    assert [item["plan"]["author"]["first_name"] for item in bianca] == ["Bob"]
    assert alice == []


# --- Who may see a plan ------------------------------------------------------------------------


async def test_drafts_are_private_to_their_author(world, db):
    draft = await make_plan(db, world.acme, world.alice, week_start=NEXT_WEEK)
    for user in (world.lead, world.owner, world.admin, world.beta_lead):
        response = await world.as_(user).get(plan_url(world, draft))
        assert response.status_code == 404
    assert (await world.as_(world.alice).get(plan_url(world, draft))).status_code == 200


async def test_submitted_plans_are_shared_with_teammates_and_managers_only(world):
    url = plan_url(world, world.alice_plan)
    for user in (world.lead, world.beta_lead, world.owner, world.admin):
        response = await world.as_(user).get(url)
        assert response.status_code == 200, user.first_name
        assert response.json()["permissions"]["can_edit"] is False
    # Bob shares no team with Alice.
    assert (await world.as_(world.bob).get(url)).status_code == 404


async def test_only_the_author_ticks_tasks(world, db):
    task_id = await db.scalar(
        select(PlanTask.id).where(PlanTask.plan_id == world.alice_plan.id).limit(1)
    )
    response = await world.as_(world.lead).patch(
        plan_url(world, world.alice_plan, f"/tasks/{task_id}"), json={"status": "done"}
    )
    assert response.status_code == 403


async def test_history_lists_own_plans_newest_first(world, db):
    await make_plan(
        db, world.acme, world.alice, week_start=THIS_WEEK - timedelta(weeks=1)
    )
    response = await world.as_(world.alice).get(
        f"/organizations/{world.acme.id}/me/plans"
    )
    body = response.json()
    assert body["total"] == 2
    weeks = [item["week_start"] for item in body["items"]]
    assert weeks == sorted(weeks, reverse=True)


async def test_database_rejects_a_non_monday_week_even_without_the_api(world, db):
    with pytest.raises(IntegrityError, match="ck_weekly_plans_week_start_monday"):
        await make_plan(
            db, world.acme, world.bob, week_start=THIS_WEEK + timedelta(days=2)
        )
