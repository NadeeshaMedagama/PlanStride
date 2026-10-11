from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ValidationException
from app.models import Membership, User
from app.services.organizations import OrganizationService
from app.services.users import UserService


class AccountService:
    """Public sign-up. Always creates a customer account: platform staff are
    only ever created with `manage.py create-user --admin`."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sign_up(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        organization_name: str | None,
        invite_token: str | None,
    ) -> tuple[User, Membership]:
        """Create the account and, in the same transaction, either a new
        organization it owns or a membership through an invite."""
        if not organization_name and not invite_token:
            raise ValidationException(
                "Name your organization or use an invite link to join one."
            )
        organizations = OrganizationService(self.session)
        # Resolve the invite first: a bad link fails before an account exists.
        invitation = (
            await organizations.get_valid_invitation(invite_token, for_update=True)
            if invite_token
            else None
        )
        user = await UserService(self.session).create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            is_active=True,
        )
        if invitation is not None:
            membership = await organizations.join_with_invitation(user, invitation)
        else:
            membership = await organizations.create_organization(
                owner=user, name=organization_name or ""
            )
        return user, membership
