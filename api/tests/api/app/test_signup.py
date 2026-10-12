from datetime import timedelta

from sqlalchemy import select

from app.domain import utcnow
from app.models import Invitation, Membership, Organization, User
from app.security import hash_invite_token
from tests.factories import PASSWORD, error_code, make_user


def signup_body(**overrides):
    body = {
        "first_name": "Nia",
        "last_name": "Walker",
        "email": "nia@example.com",
        "password": "long-enough-1",
        "organization_name": "Walker Robotics",
    }
    body.update(overrides)
    return body


async def invite(db, organization_id, token="tok-123", **fields):
    invitation = Invitation(
        organization_id=organization_id,
        role=fields.pop("role", "member"),
        token_hash=hash_invite_token(token),
        expires_at=fields.pop("expires_at", utcnow() + timedelta(days=7)),
        **fields,
    )
    db.add(invitation)
    await db.commit()
    return invitation


async def test_signup_creates_account_and_organization_owned_by_it(async_client, db):
    response = await async_client.post("/app/signup", json=signup_body())

    assert response.status_code == 201
    assert "access_token" in response.json()
    assert "access_token" in response.cookies  # signed straight in

    user = await db.scalar(select(User).where(User.email == "nia@example.com"))
    assert user is not None
    assert user.is_active and not user.is_platform_staff
    assert user.last_login_at is not None
    membership = await db.scalar(
        select(Membership).where(Membership.user_id == user.id)
    )
    assert membership is not None and membership.role == "owner"
    organization = await db.get(Organization, membership.organization_id)
    assert organization is not None and organization.name == "Walker Robotics"

    me = await async_client.get("/app/organizations")
    assert [org["role"] for org in me.json()] == ["owner"]


async def test_signup_can_never_create_platform_staff(async_client, db):
    response = await async_client.post(
        "/app/signup",
        json=signup_body(is_platform_staff=True, is_admin=True, is_active=False),
    )
    assert response.status_code == 201
    user = await db.scalar(select(User).where(User.email == "nia@example.com"))
    assert user is not None
    assert user.is_platform_staff is False
    assert user.is_active is True


async def test_signup_with_invite_joins_with_the_invited_role(async_client, db):
    owner = await make_user(db)
    organization = Organization(name="Acme")
    db.add(organization)
    await db.flush()
    db.add(Membership(organization_id=organization.id, user_id=owner.id, role="owner"))
    await db.commit()
    invitation = await invite(db, organization.id, role="admin")

    response = await async_client.post(
        "/app/signup",
        json=signup_body(organization_name=None, invite_token="tok-123"),
    )

    assert response.status_code == 201
    orgs = (await async_client.get("/app/organizations")).json()
    assert orgs == [
        {
            "id": str(organization.id),
            "name": "Acme",
            "role": "admin",
            "is_suspended": False,
        }
    ]
    await db.refresh(invitation)
    assert invitation.accepted_at is not None
    # No organization was created along the way.
    assert (
        await db.scalar(
            select(Organization).where(Organization.name == "Walker Robotics")
        )
        is None
    )


async def test_signup_with_bad_invite_creates_nothing(async_client, db):
    response = await async_client.post(
        "/app/signup",
        json=signup_body(organization_name=None, invite_token="nope"),
    )
    assert response.status_code == 404
    assert await db.scalar(select(User).where(User.email == "nia@example.com")) is None


async def test_signup_needs_exactly_one_way_in(async_client):
    neither = await async_client.post(
        "/app/signup", json=signup_body(organization_name=None)
    )
    both = await async_client.post(
        "/app/signup", json=signup_body(invite_token="tok-123")
    )
    assert neither.status_code == 422
    assert both.status_code == 422


async def test_signup_rejects_duplicate_email_and_short_password(async_client, db):
    await make_user(db, email="nia@example.com")
    duplicate = await async_client.post("/app/signup", json=signup_body())
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"][0]["loc"] == ["body", "email"]

    short = await async_client.post(
        "/app/signup", json=signup_body(email="new@example.com", password="short")
    )
    assert short.status_code == 422


async def test_login_records_last_login(async_client, db):
    user = await make_user(db, email="kim@example.com")
    response = await async_client.post(
        "/app/auth", json={"email": "KIM@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    await db.refresh(user)
    assert user.last_login_at is not None


async def test_deactivated_user_cannot_sign_in(async_client, db):
    await make_user(db, email="gone@example.com", active=False)

    right_password = await async_client.post(
        "/app/auth", json={"email": "gone@example.com", "password": PASSWORD}
    )
    wrong_password = await async_client.post(
        "/app/auth", json={"email": "gone@example.com", "password": "wrong-password"}
    )

    assert right_password.status_code == 403
    assert error_code(right_password) == "account_deactivated"
    # Deactivation is only revealed to someone who knows the password.
    assert wrong_password.status_code == 401
    assert error_code(wrong_password) == "invalid_credentials"
