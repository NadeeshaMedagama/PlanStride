"""Staff suspend an organization from the internal console; its members are
locked out of it (and only it) until it's reinstated."""

from tests.factories import add_member, error_code


async def suspend(world):
    response = await world.as_staff().post(
        f"/organizations/{world.acme.id}/suspend", json={"reason": "Chargeback"}
    )
    assert response.status_code == 200


async def test_suspended_organization_locks_out_every_member(world):
    await suspend(world)
    for user in (world.owner, world.admin, world.lead, world.alice):
        actor = world.as_(user)
        for response in (
            await actor.get(f"/organizations/{world.acme.id}"),
            await actor.get(f"/organizations/{world.acme.id}/teams"),
            await actor.get(
                f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}"
            ),
            await actor.post(
                f"/organizations/{world.acme.id}/plans/{world.alice_plan.id}/approve",
                json={},
            ),
        ):
            assert response.status_code == 403
            assert error_code(response) == "organization_suspended"


async def test_suspended_organization_still_listed_so_the_ui_can_explain(world):
    await suspend(world)
    response = await world.as_(world.alice).get("/organizations")
    assert response.json()[0]["is_suspended"] is True


async def test_suspension_is_per_organization(world, db):
    await add_member(db, world.globex, world.alice)
    await suspend(world)
    response = await world.as_(world.alice).get(f"/organizations/{world.globex.id}")
    assert response.status_code == 200


async def test_reinstating_restores_access(world):
    await suspend(world)
    reinstate = await world.as_staff().post(f"/organizations/{world.acme.id}/reinstate")
    assert reinstate.status_code == 200
    assert (
        await world.as_(world.alice).get(f"/organizations/{world.acme.id}")
    ).status_code == 200


async def test_suspended_organization_takes_no_new_members(world):
    token = (
        await world.as_(world.owner).post(
            f"/organizations/{world.acme.id}/invitations", json={}
        )
    ).json()["token"]
    await suspend(world)
    response = await world.as_(world.carol).post(f"/invitations/{token}/accept")
    assert response.status_code == 403
