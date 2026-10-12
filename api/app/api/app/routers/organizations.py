import uuid

from fastapi import APIRouter, status

from app.api.app.access import CurrentUser, OrgManager, OrgMember
from app.api.app.presenters import invitation_response, user_summary
from app.api.app.schemas import (
    InvitationCreatedResponse,
    InvitationCreateRequest,
    InvitationResponse,
    MemberResponse,
    MemberUpdateRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationSummary,
    OrganizationUpdateRequest,
    TeamRef,
)
from app.database import DBSession
from app.services.organizations import MemberRow, OrganizationService
from app.tenancy import OrgAccess

router = APIRouter()


async def _organization_response(
    service: OrganizationService, access: OrgAccess
) -> OrganizationResponse:
    members, teams = await service.counts(access.organization_id)
    return OrganizationResponse(
        id=access.organization.id,
        name=access.organization.name,
        created_at=access.organization.created_at,
        role=access.role,
        member_count=members,
        team_count=teams,
    )


def _member_response(row: MemberRow) -> MemberResponse:
    return MemberResponse(
        user=user_summary(row.user),
        role=row.membership.role,
        joined_at=row.membership.created_at,
        teams=[TeamRef(id=team.id, name=team.name) for team in row.teams],
        is_active=row.user.is_active,
    )


# --- Organizations ---------------------------------------------------------------------


@router.get("/organizations", tags=["organizations"])
async def organization_list(
    current_user: CurrentUser, session: DBSession
) -> list[OrganizationSummary]:
    """The organizations the caller belongs to, with their role in each."""
    rows = await OrganizationService(session).list_for_user(current_user.id)
    return [
        OrganizationSummary(
            id=organization.id,
            name=organization.name,
            role=membership.role,
            is_suspended=organization.is_suspended,
        )
        for membership, organization in rows
    ]


@router.post(
    "/organizations", status_code=status.HTTP_201_CREATED, tags=["organizations"]
)
async def organization_create(
    current_user: CurrentUser, session: DBSession, data: OrganizationCreateRequest
) -> OrganizationSummary:
    membership = await OrganizationService(session).create_organization(
        owner=current_user, name=data.name
    )
    await session.commit()
    return OrganizationSummary(
        id=membership.organization.id,
        name=membership.organization.name,
        role=membership.role,
        is_suspended=False,
    )


@router.get("/organizations/{organization_id}", tags=["organizations"])
async def organization_get(
    access: OrgMember, session: DBSession
) -> OrganizationResponse:
    return await _organization_response(OrganizationService(session), access)


@router.patch("/organizations/{organization_id}", tags=["organizations"])
async def organization_update(
    access: OrgManager, session: DBSession, data: OrganizationUpdateRequest
) -> OrganizationResponse:
    service = OrganizationService(session)
    await service.rename(access.organization, data.name)
    await session.commit()
    return await _organization_response(service, access)


# --- Members ---------------------------------------------------------------------------


@router.get("/organizations/{organization_id}/members", tags=["members"])
async def member_list(access: OrgMember, session: DBSession) -> list[MemberResponse]:
    rows = await OrganizationService(session).list_members(access.organization_id)
    return [_member_response(row) for row in rows]


@router.patch("/organizations/{organization_id}/members/{user_id}", tags=["members"])
async def member_update(
    access: OrgManager,
    session: DBSession,
    user_id: uuid.UUID,
    data: MemberUpdateRequest,
) -> MemberResponse:
    """Change a member's role. Admins can't touch owners or make new ones; the
    last owner can't be demoted."""
    service = OrganizationService(session)
    await service.change_role(access, user_id, data.role)
    await session.commit()
    return _member_response(await service.get_member(access.organization_id, user_id))


@router.delete(
    "/organizations/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["members"],
)
async def member_remove(
    access: OrgManager, session: DBSession, user_id: uuid.UUID
) -> None:
    await OrganizationService(session).remove_member(access, user_id)
    await session.commit()


# --- Invitations -------------------------------------------------------------------------


@router.get("/organizations/{organization_id}/invitations", tags=["invitations"])
async def invitation_list(
    access: OrgManager, session: DBSession
) -> list[InvitationResponse]:
    invitations = await OrganizationService(session).list_invitations(
        access.organization_id
    )
    return [invitation_response(invitation) for invitation in invitations]


@router.post(
    "/organizations/{organization_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    tags=["invitations"],
)
async def invitation_create(
    access: OrgManager, session: DBSession, data: InvitationCreateRequest
) -> InvitationCreatedResponse:
    """Create a single-use invite link, valid for 7 days. The token is in this
    response only; share the link built from it."""
    invitation, token = await OrganizationService(session).create_invitation(
        access, data.role
    )
    await session.commit()
    return InvitationCreatedResponse(
        **invitation_response(invitation).model_dump(), token=token
    )


@router.delete(
    "/organizations/{organization_id}/invitations/{invitation_id}",
    tags=["invitations"],
)
async def invitation_revoke(
    access: OrgManager, session: DBSession, invitation_id: uuid.UUID
) -> InvitationResponse:
    invitation = await OrganizationService(session).revoke_invitation(
        access.organization_id, invitation_id
    )
    await session.commit()
    return invitation_response(invitation)
