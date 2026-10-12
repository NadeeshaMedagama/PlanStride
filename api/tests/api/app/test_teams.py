from datetime import timedelta

from app.domain import current_week_start
from tests.factories import make_plan

THIS_WEEK = current_week_start()


def teams_url(world, suffix=""):
    return f"/organizations/{world.acme.id}/teams{suffix}"


async def test_team_list_flags_the_callers_teams(world):
    response = await world.as_(world.beta_lead).get(teams_url(world))
    teams = {team["name"]: team for team in response.json()}
    assert teams["Alpha"]["is_member"] and not teams["Alpha"]["is_lead"]
    assert teams["Beta"]["is_member"] and teams["Beta"]["is_lead"]
    assert teams["Alpha"]["member_count"] == 3
    assert teams["Alpha"]["lead"]["first_name"] == "Leah"


async def test_admins_create_teams_with_a_lead_who_joins_automatically(world):
    response = await world.as_(world.admin).post(
        teams_url(world),
        json={
            "name": "Growth",
            "description": "Activation and onboarding.",
            "lead_user_id": str(world.bob.id),
            "member_ids": [str(world.alice.id)],
        },
    )
    assert response.status_code == 201
    team = response.json()
    assert team["lead"]["id"] == str(world.bob.id)
    assert {member["id"] for member in team["members"]} == {
        str(world.bob.id),
        str(world.alice.id),
    }


async def test_members_cannot_manage_teams(world):
    alice = world.as_(world.alice)
    attempts = [
        await alice.post(teams_url(world), json={"name": "Shadow"}),
        await alice.patch(
            teams_url(world, f"/{world.alpha.id}"), json={"name": "Mine"}
        ),
        await alice.delete(teams_url(world, f"/{world.alpha.id}")),
        await alice.put(teams_url(world, f"/{world.alpha.id}/members/{world.bob.id}")),
        await alice.delete(
            teams_url(world, f"/{world.alpha.id}/members/{world.lead.id}")
        ),
    ]
    assert [response.status_code for response in attempts] == [403] * 5


async def test_team_leads_cannot_manage_their_own_team(world):
    """Leads approve plans; changing who's on the team is an admin's call."""
    response = await world.as_(world.lead).put(
        teams_url(world, f"/{world.alpha.id}/members/{world.bob.id}")
    )
    assert response.status_code == 403


async def test_team_names_are_unique_per_organization(world):
    admin = world.as_(world.admin)
    duplicate = await admin.post(teams_url(world), json={"name": "alpha"})
    assert duplicate.status_code == 409
    # Another organization can use the same name.
    other = await world.as_(world.owner_b).post(
        f"/organizations/{world.globex.id}/teams", json={"name": "Alpha"}
    )
    assert other.status_code == 201


async def test_a_user_can_be_on_several_teams(world):
    response = await world.as_(world.admin).put(
        teams_url(world, f"/{world.beta.id}/members/{world.alice.id}")
    )
    assert response.status_code == 200
    members = await world.as_(world.alice).get(
        f"/organizations/{world.acme.id}/members"
    )
    alice = next(
        row for row in members.json() if row["user"]["id"] == str(world.alice.id)
    )
    assert {team["name"] for team in alice["teams"]} == {"Alpha", "Beta"}


async def test_changing_and_clearing_the_lead(world):
    admin = world.as_(world.admin)
    url = teams_url(world, f"/{world.alpha.id}")
    new_lead = await admin.patch(url, json={"lead_user_id": str(world.alice.id)})
    assert new_lead.json()["lead"]["id"] == str(world.alice.id)

    cleared = await admin.patch(url, json={"lead_user_id": None})
    assert cleared.json()["lead"] is None
    # Leaving lead out of the patch leaves it alone.
    renamed = await admin.patch(url, json={"name": "Alpha Squad"})
    assert renamed.json()["lead"] is None and renamed.json()["name"] == "Alpha Squad"


async def test_removing_the_lead_from_the_team_clears_the_lead(world):
    response = await world.as_(world.admin).delete(
        teams_url(world, f"/{world.alpha.id}/members/{world.lead.id}")
    )
    assert response.status_code == 200
    assert response.json()["lead"] is None


# --- The team's week ----------------------------------------------------------------------


async def test_team_week_shows_everyone_at_a_glance(world, db):
    await make_plan(
        db, world.acme, world.beta_lead, status="draft", main_task="Secret draft"
    )
    response = await world.as_(world.lead).get(
        teams_url(world, f"/{world.alpha.id}/weeks/{THIS_WEEK.isoformat()}")
    )
    assert response.status_code == 200
    week = response.json()
    assert week["viewer_is_lead"] is True
    rows = {row["member"]["first_name"]: row for row in week["members"]}

    assert rows["Alice"]["plan"]["status"] == "submitted"
    assert rows["Alice"]["plan"]["main_task"].startswith("Checkout handles")
    assert rows["Alice"]["plan"]["tasks_total"] == 3
    # A draft shows as a draft, without its content.
    assert rows["Bianca"]["plan"]["status"] == "draft"
    assert rows["Bianca"]["plan"]["main_task"] is None
    assert rows["Leah"]["plan"] is None and rows["Leah"]["is_lead"] is True

    assert week["stats"] == {
        "members": 3,
        "planned": 2,
        "submitted": 1,
        "approved": 0,
        "done": 0,
        "shipped": 0,
        "tasks_done": 0,
        "tasks_total": 3,
    }


async def test_team_week_visible_to_members_and_managers_only(world):
    url = teams_url(world, f"/{world.alpha.id}/weeks/{THIS_WEEK.isoformat()}")
    assert (await world.as_(world.alice).get(url)).status_code == 200
    assert (await world.as_(world.admin).get(url)).status_code == 200
    outsider = await world.as_(world.bob).get(url)
    assert outsider.status_code == 403


async def test_team_week_requires_a_monday(world):
    tuesday = THIS_WEEK + timedelta(days=1)
    response = await world.as_(world.lead).get(
        teams_url(world, f"/{world.alpha.id}/weeks/{tuesday.isoformat()}")
    )
    assert response.status_code == 400


async def test_team_history_counts_past_weeks(world, db):
    last_week = THIS_WEEK - timedelta(weeks=1)
    shipped = await make_plan(
        db, world.acme, world.alice, week_start=last_week, status="done"
    )
    shipped.main_task_shipped = True
    unshipped = await make_plan(
        db, world.acme, world.beta_lead, week_start=last_week, status="done"
    )
    unshipped.main_task_shipped = False
    await db.commit()

    response = await world.as_(world.lead).get(
        teams_url(world, f"/{world.alpha.id}/history"), params={"weeks": 3}
    )
    weeks = response.json()["weeks"]
    assert [week["week_start"] for week in weeks] == [
        (THIS_WEEK - timedelta(weeks=n)).isoformat() for n in range(3)
    ]
    assert weeks[1]["done"] == 2
    assert weeks[1]["shipped"] == 1
    assert weeks[0]["submitted"] == 1
    assert weeks[2]["planned"] == 0
