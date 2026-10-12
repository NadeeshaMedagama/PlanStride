from fastapi import APIRouter

from app.api.app.access import CurrentUser
from app.api.app.schemas import InvitationPreviewResponse, OrganizationSummary
from app.database import DBSession
from app.services.organizations import OrganizationService

router = APIRouter()


@router.get("/invitations/{token}", tags=["invitations"])
async def invitation_preview(
    token: str, session: DBSession
) -> InvitationPreviewResponse:
    """What an invite link leads to, shown before signing up or in. Public:
    the token itself is the credential, and only the organization's name and
    the role on offer are revealed."""
    invitation = await OrganizationService(session).get_valid_invitation(token)
    inviter = invitation.created_by
    return InvitationPreviewResponse(
        organization_name=invitation.organization.name,
        role=invitation.role,
        invited_by=inviter.full_name if inviter else None,
        expires_at=invitation.expires_at,
    )


@router.post("/invitations/{token}/accept", tags=["invitations"])
async def invitation_accept(
    token: str, current_user: CurrentUser, session: DBSession
) -> OrganizationSummary:
    """Join the organization behind an invite link as the signed-in user."""
    membership = await OrganizationService(session).accept_invitation(
        current_user, token
    )
    await session.commit()
    return OrganizationSummary(
        id=membership.organization.id,
        name=membership.organization.name,
        role=membership.role,
        is_suspended=False,
    )
