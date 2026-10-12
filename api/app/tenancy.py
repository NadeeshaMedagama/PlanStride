"""The caller's tenancy context, resolved per request by the app API.

Kept out of `app.api` so services can take it as a plain argument: a service
method that receives an `OrgAccess` scopes every query to
`access.organization_id` and makes role decisions from `access.role`.
"""

import uuid
from dataclasses import dataclass

from app.domain import ORG_MANAGER_ROLES, ORG_ROLE_OWNER, OrgRole
from app.models import Membership, Organization, User


@dataclass(frozen=True)
class OrgAccess:
    """The caller, the organization they're acting in, and their role in it."""

    user: User
    organization: Organization
    membership: Membership

    @property
    def organization_id(self) -> uuid.UUID:
        return self.organization.id

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def role(self) -> OrgRole:
        return self.membership.role

    @property
    def is_owner(self) -> bool:
        return self.membership.role == ORG_ROLE_OWNER

    @property
    def can_manage(self) -> bool:
        """Owner or admin of this organization: a customer role, unrelated to
        platform staff."""
        return self.membership.role in ORG_MANAGER_ROLES
