from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.models import Organization, Team, User, WeeklyPlan
from tests.factories import Actor, add_member, make_org, make_plan, make_team, make_user


@dataclass
class World:
    """Two customer organizations and a staff user, with every role covered.

    Acme
      owner, admin (no team), lead (leads Alpha), alice (Alpha),
      beta_lead (leads Beta, also on Alpha), bob (Beta)
    Globex
      owner_b, lead_b (leads Gamma), carol (Gamma)

    Alice and Carol each have a submitted plan for this week.
    """

    acme: Organization
    globex: Organization
    alpha: Team
    beta: Team
    gamma: Team
    owner: User
    admin: User
    lead: User
    alice: User
    beta_lead: User
    bob: User
    owner_b: User
    lead_b: User
    carol: User
    staff: User
    alice_plan: WeeklyPlan
    carol_plan: WeeklyPlan
    client: AsyncClient

    def as_(self, user: User) -> Actor:
        return Actor(self.client, user)

    def as_staff(self, user: User | None = None) -> Actor:
        return Actor(self.client, user or self.staff, surface="internal")


@pytest.fixture
async def world(db, async_client) -> World:
    owner = await make_user(db, "Olivia")
    admin = await make_user(db, "Adam")
    lead = await make_user(db, "Leah")
    alice = await make_user(db, "Alice")
    beta_lead = await make_user(db, "Bianca")
    bob = await make_user(db, "Bob")
    acme = await make_org(db, "Acme", owner=owner)
    await add_member(db, acme, admin, "admin")
    for user in (lead, alice, beta_lead, bob):
        await add_member(db, acme, user)
    alpha = await make_team(db, acme, "Alpha", lead=lead, members=[alice, beta_lead])
    beta = await make_team(db, acme, "Beta", lead=beta_lead, members=[bob])

    owner_b = await make_user(db, "Grace")
    lead_b = await make_user(db, "Gary")
    carol = await make_user(db, "Carol")
    globex = await make_org(db, "Globex", owner=owner_b)
    await add_member(db, globex, lead_b)
    await add_member(db, globex, carol)
    gamma = await make_team(db, globex, "Gamma", lead=lead_b, members=[carol])

    staff = await make_user(db, "Sam", staff=True)
    alice_plan = await make_plan(db, acme, alice, status="submitted")
    carol_plan = await make_plan(db, globex, carol, status="submitted")

    return World(
        acme=acme,
        globex=globex,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        owner=owner,
        admin=admin,
        lead=lead,
        alice=alice,
        beta_lead=beta_lead,
        bob=bob,
        owner_b=owner_b,
        lead_b=lead_b,
        carol=carol,
        staff=staff,
        alice_plan=alice_plan,
        carol_plan=carol_plan,
        client=async_client,
    )
