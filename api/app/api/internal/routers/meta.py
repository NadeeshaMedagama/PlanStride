from fastapi import APIRouter, Response, status
from sqlalchemy import select, text

from app.api.internal.schemas import AuthRequest, AuthResponse
from app.config import settings
from app.database import DBSession
from app.domain import utcnow
from app.exceptions import APIException
from app.logging import logger
from app.models import User
from app.schemas import HealthCheckResponse, MessageResponse
from app.security import (
    JWT_AUDIENCE_INTERNAL,
    burn_password_check,
    generate_jwt_token,
    verify_password,
)

# Internal sessions use a dedicated cookie so a staff member can hold app and
# internal sessions at once without one overwriting the other.
INTERNAL_COOKIE_NAME = "internal_access_token"

router = APIRouter()


@router.get("/health", tags=["meta"])
async def health(session: DBSession, response: Response) -> HealthCheckResponse:
    try:
        # Check database connectivity
        await session.execute(text("SELECT 1"))
        return HealthCheckResponse(status="healthy")

    except Exception:
        # Log the traceback internally but don't expose details
        logger.exception("Internal health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthCheckResponse(status="unhealthy")


@router.post("/auth", tags=["auth"])
async def auth(
    auth_request: AuthRequest, session: DBSession, response: Response
) -> AuthResponse:
    result = await session.execute(
        select(User).where(
            User.email == auth_request.email.lower(),
        )
    )
    user = result.scalars().first()

    # Exactly one Argon2 verification on every path, so response time doesn't
    # reveal which emails belong to staff accounts.
    if user is None or user.password is None:
        burn_password_check(auth_request.password)
        password_ok = False
    else:
        password_ok = verify_password(auth_request.password, user.password)

    # Only active platform staff may authenticate against the internal surface.
    # Anyone else (customer owners and admins included) gets the same generic
    # error as bad credentials, so account state isn't disclosed.
    if user is not None and password_ok and user.is_platform_staff and user.is_active:
        user.last_login_at = utcnow()
        await session.commit()
        access_token = generate_jwt_token(
            {"sub": str(user.id)}, audience=JWT_AUDIENCE_INTERNAL
        )
        response.set_cookie(
            key=INTERNAL_COOKIE_NAME,
            value=f"Bearer {access_token}",
            samesite="lax",
            secure=settings.SECURE_COOKIE,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        )
        return AuthResponse(access_token=access_token)
    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="INVALID_CREDENTIALS",
        message="Incorrect username or password",
    )


@router.post("/logout", tags=["auth"])
async def logout(response: Response) -> MessageResponse:
    response.delete_cookie(INTERNAL_COOKIE_NAME)
    return MessageResponse(message="Successfully logged out")
