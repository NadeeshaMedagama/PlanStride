from typing import Annotated

from fastapi import Depends, status

from app.api.app.access import build_http_user_dependency
from app.exceptions import APIException
from app.models import User
from app.security import JWT_AUDIENCE_INTERNAL

http_staff_required_exception = APIException(
    status_code=status.HTTP_403_FORBIDDEN,
    code="PLATFORM_STAFF_REQUIRED",
    message="Platform staff access required",
)

# Internal surface: `internal_access_token` cookie, internal-audience tokens. An app
# token (different audience, different cookie) never resolves a user here.
get_current_http_user = build_http_user_dependency(
    audience=JWT_AUDIENCE_INTERNAL, cookie_name="internal_access_token"
)


async def get_current_internal_user(
    user: Annotated[User, Depends(get_current_http_user)],
) -> User:
    # Token audience already restricts callers to the internal surface; the flag is
    # a second gate so a non-staff user who somehow holds an internal-audience
    # token (e.g. a stale grant) is still refused. Being an owner or admin of a
    # customer organization grants nothing here.
    if not user.is_platform_staff:
        raise http_staff_required_exception
    return user


CurrentInternalUser = Annotated[User, Depends(get_current_internal_user)]
