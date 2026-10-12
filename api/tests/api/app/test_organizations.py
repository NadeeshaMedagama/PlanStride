from datetime import timedelta

from sqlalchemy import select

from app.domain import utcnow
from app.models import Invitation, Membership, Team, TeamMembership
from app.security import hash_invite_token
from tests.factories import error_code, make_user


def org_url(world, suffix=""):
    return f"/organizations/{world.acme.id}{suffix}"


# --- Organization settings ----------------------------------------------------------


async def test_member_sees_organization_with_their_role(world):
    response = await world.as_(world.alice).get(org_url(world))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "member"
    assert body["member_count"] == 6
    assert body["team_count"] == 2


async def test_only_owners_and_admins_rename_the_organization(world):
    member = await world.as_(world.alice).patch(org_url(world), json={"name": "Mine"})
    admin = await world.as_(world.admin).patch(
        org_url(world), json={"name": "Acme Inc"}
    )

    assert member.status_code == 403
    assert error_code(member) == "org_manager_required"
    assert admin.status_code == 200
    assert admin.json()["name"] == "Acme Inc"


async def test_a_user_can_start_another_organization(world):
    response = await world.as_(world.alice).post(
        "/organizations", json={"name": "Side Project"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "owner"
    names = {
        org["name"]
        for org in (await world.as_(world.alice).get("/organizations")).json()
    }
    assert names == {"Acme", "Side Project"}


# --- Members and roles --------------------------------------------------------------


async def test_members_list_shows_roles_and_teams(world):
    response = await world.as_(world.alice).get(org_url(world, "/members"))
    assert response.status_code == 200
    by_name = {row["user"]["first_name"]: row for row in response.json()}
    assert by_name["Olivia"]["role"] == "owner"
    assert by_name["Adam"]["role"] == "admin"
    assert {team["name"] for team in by_name["Bianca"]["teams"]} == {"Alpha", "Beta"}
    assert all(row["is_active"] for row in response.json())


async def test_member_cannot_change_roles(world):
    response = await world.as_(world.alice).patch(
        org_url(world, f"/members/{world.bob.id}"), json={"role": "admin"}
    )
    assert response.status_code == 403


async def test_admin_manages_members_but_not_owners(world):
    admin = world.as_(world.admin)
    promote = await admin.patch(
        org_url(world, f"/members/{world.bob.id}"), json={"role": "admin"}
    )
    make_owner = await admin.patch(
        org_url(world, f"/members/{world.bob.id}"), json={"role": "owner"}
    )
    demote_owner = await admin.patch(
        org_url(world, f"/members/{world.owner.id}"), json={"role": "member"}
    )
    remove_owner = await admin.delete(org_url(world, f"/members/{world.owner.id}"))

    assert promote.status_code == 200 and promote.json()["role"] == "admin"
    assert make_owner.status_code == 403
    assert demote_owner.status_code == 403
    assert remove_owner.status_code == 403


async def test_owner_can_make_another_owner_then_step_down(world):
    owner = world.as_(world.owner)
    assert (
        await owner.patch(
            org_url(world, f"/members/{world.admin.id}"), json={"role": "owner"}
        )
    ).status_code == 200
    step_down = await owner.patch(
        org_url(world, f"/members/{world.owner.id}"), json={"role": "member"}
    )
    assert step_down.status_code == 200


async def test_last_owner_cannot_be_demoted_or_removed(world):
    owner = world.as_(world.owner)
    demote = await owner.patch(
        org_url(world, f"/members/{world.owner.id}"), json={"role": "admin"}
    )
    remove = await owner.delete(org_url(world, f"/members/{world.owner.id}"))
    assert demote.status_code == 409
    assert "at least one owner" in demote.json()["detail"][0]["msg"]
    assert remove.status_code == 409


async def test_removing_a_member_removes_their_seats_and_leadership(world, db):
    response = await world.as_(world.admin).delete(
        org_url(world, f"/members/{world.beta_lead.id}")
    )
    assert response.status_code == 204

    seats = await db.scalars(
        select(TeamMembership).where(TeamMembership.user_id == world.beta_lead.id)
    )
    assert seats.all() == []
    beta = await db.get(Team, world.beta.id, populate_existing=True)
    assert beta is not None and beta.lead_user_id is None
    # They no longer get in at all.
    assert (await world.as_(world.beta_lead).get(org_url(world))).status_code == 404


# --- Invitations -----------------------------------------------------------------------


async def test_admin_creates_single_use_invite_and_only_its_hash_is_stored(world, db):
    response = await world.as_(world.admin).post(
        org_url(world, "/invitations"), json={"role": "member"}
    )
    assert response.status_code == 201
    body = response.json()
    token = body["token"]
    assert body["status"] == "pending"

    stored = await db.get(Invitation, body["id"])
    assert stored is not None
    assert stored.token_hash == hash_invite_token(token)
    assert token not in stored.token_hash

    listed = await world.as_(world.admin).get(org_url(world, "/invitations"))
    assert all("token" not in invitation for invitation in listed.json())


async def test_members_cannot_invite_and_nobody_can_invite_an_owner(world):
    member = await world.as_(world.alice).post(
        org_url(world, "/invitations"), json={"role": "member"}
    )
    as_owner = await world.as_(world.owner).post(
        org_url(world, "/invitations"), json={"role": "owner"}
    )
    assert member.status_code == 403
    assert as_owner.status_code == 422


async def test_invite_preview_and_accept(world, db, async_client):
    token = (
        await world.as_(world.owner).post(
            org_url(world, "/invitations"), json={"role": "admin"}
        )
    ).json()["token"]

    preview = await async_client.get(f"/app/invitations/{token}")
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Acme"
    assert preview.json()["role"] == "admin"

    newcomer = await make_user(db, "Nora")
    accepted = await world.as_(newcomer).post(f"/invitations/{token}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "admin"

    # Single use: the link is dead now, for the next person and for preview.
    again = await world.as_(await make_user(db, "Late")).post(
        f"/invitations/{token}/accept"
    )
    assert again.status_code == 404
    assert (await async_client.get(f"/app/invitations/{token}")).status_code == 404


async def test_invite_cannot_be_accepted_by_an_existing_member(world):
    token = (
        await world.as_(world.owner).post(org_url(world, "/invitations"), json={})
    ).json()["token"]
    response = await world.as_(world.alice).post(f"/invitations/{token}/accept")
    assert response.status_code == 409


async def test_expired_and_revoked_invites_are_refused(world, db):
    expired = Invitation(
        organization_id=world.acme.id,
        role="member",
        token_hash=hash_invite_token("old-link"),
        expires_at=utcnow() - timedelta(minutes=1),
    )
    db.add(expired)
    await db.commit()
    newcomer = world.as_(await make_user(db, "Nora"))
    assert (await newcomer.post("/invitations/old-link/accept")).status_code == 404

    created = (
        await world.as_(world.owner).post(org_url(world, "/invitations"), json={})
    ).json()
    revoke = await world.as_(world.owner).delete(
        org_url(world, f"/invitations/{created['id']}")
    )
    assert revoke.status_code == 200 and revoke.json()["status"] == "revoked"
    assert (
        await newcomer.post(f"/invitations/{created['token']}/accept")
    ).status_code == 404

    memberships = await db.scalars(
        select(Membership).where(Membership.user_id == newcomer.user.id)
    )
    assert memberships.all() == []
