import uuid

from fastapi import APIRouter, Query, status

from app.api.internal.access import CurrentInternalUser
from app.api.internal.schemas import (
    InternalUserResponse,
    UserChangePasswordRequest,
    UserMembershipResponse,
    UsersListResponse,
    UserUpdateRequest,
)
from app.database import DBSession
from app.models import User
from app.services.users import UserMembership, UserService

router = APIRouter()


def _user_response(
    user: User, memberships: list[UserMembership]
) -> InternalUserResponse:
    return InternalUserResponse(
        id=user.id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        is_platform_staff=user.is_platform_staff,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        memberships=[
            UserMembershipResponse(
                organization_id=membership.organization_id,
                organization_name=membership.organization_name,
                role=membership.role,
                is_suspended=membership.is_suspended,
            )
            for membership in memberships
        ],
    )


async def _respond(service: UserService, user: User) -> InternalUserResponse:
    memberships = await service.memberships_for([user.id])
    return _user_response(user, memberships.get(user.id, []))


@router.get("/users/self", tags=["users"])
async def get_current_internal_user(
    current_user: CurrentInternalUser, session: DBSession
) -> InternalUserResponse:
    return await _respond(UserService(session), current_user)


@router.get("/users", tags=["users"])
async def user_list(
    current_user: CurrentInternalUser,
    session: DBSession,
    search: str | None = Query(None, max_length=100, description="Name or email"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> UsersListResponse:
    service = UserService(session)
    users, total = await service.list_users(search=search, limit=limit, offset=offset)
    memberships = await service.memberships_for([user.id for user in users])
    return UsersListResponse(
        items=[_user_response(user, memberships.get(user.id, [])) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", tags=["users"])
async def user_get(
    current_user: CurrentInternalUser, session: DBSession, user_id: uuid.UUID
) -> InternalUserResponse:
    service = UserService(session)
    return await _respond(service, await service.get_user(user_id))


@router.patch("/users/{user_id}", tags=["users"])
async def user_update(
    current_user: CurrentInternalUser,
    session: DBSession,
    user_id: uuid.UUID,
    data: UserUpdateRequest,
) -> InternalUserResponse:
    """Edit an account or (de)activate it. A deactivated user is signed out of
    every surface at their next request."""
    service = UserService(session)
    user = await service.update_user(
        user_id, data.model_dump(exclude_unset=True), acting_user_id=current_user.id
    )
    await session.commit()
    return await _respond(service, user)


@router.post(
    "/users/{user_id}/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users"],
)
async def user_change_password(
    current_user: CurrentInternalUser,
    session: DBSession,
    user_id: uuid.UUID,
    data: UserChangePasswordRequest,
) -> None:
    """Set a new password for a user who is locked out. There is no password
    reset email (out of scope), so this is the support path."""
    await UserService(session).change_password(user_id, data.password)
    await session.commit()
