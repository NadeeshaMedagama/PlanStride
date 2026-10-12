from fastapi import APIRouter, Response, status
from sqlalchemy import select, text

from app.api.app.schemas import (
    AuthRequest,
    AuthResponse,
    SignupRequest,
)
from app.config import settings
from app.database import DBSession
from app.domain import utcnow
from app.exceptions import APIException
from app.logging import logger
from app.models import User
from app.schemas import HealthCheckResponse, MessageResponse
from app.security import (
    JWT_AUDIENCE_APP,
    burn_password_check,
    generate_jwt_token,
    verify_password,
)
from app.services.accounts import AccountService

router = APIRouter()


def _start_session(response: Response, user: User) -> str:
    access_token = generate_jwt_token({"sub": str(user.id)}, audience=JWT_AUDIENCE_APP)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        samesite="lax",
        secure=settings.SECURE_COOKIE,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
    )
    return access_token


@router.get("/health", tags=["meta"])
async def health(session: DBSession, response: Response) -> HealthCheckResponse:
    try:
        # Check database connectivity
        await session.execute(text("SELECT 1"))
        return HealthCheckResponse(status="healthy")

    except Exception:
        # Log the traceback internally but don't expose details
        logger.exception("Health check failed")
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

    if user is None or user.password is None:
        burn_password_check(auth_request.password)
    elif verify_password(auth_request.password, user.password):
        # Only said after the password checks out, so it doesn't reveal which
        # emails have accounts.
        if not user.is_active:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DEACTIVATED",
                message="This account has been deactivated. Contact PlanStride "
                "support if you think this is a mistake.",
            )
        user.last_login_at = utcnow()
        await session.commit()
        return AuthResponse(access_token=_start_session(response, user))

    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="INVALID_CREDENTIALS",
        message="Incorrect username or password",
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def signup(
    data: SignupRequest, session: DBSession, response: Response
) -> AuthResponse:
    """Create an account with email and password, then either a new
    organization (owned by the new user) or a membership through an invite.
    Signs the new user in."""
    user, _ = await AccountService(session).sign_up(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        password=data.password,
        organization_name=data.organization_name,
        invite_token=data.invite_token,
    )
    user.last_login_at = utcnow()
    await session.commit()
    return AuthResponse(access_token=_start_session(response, user))


@router.post("/logout", tags=["auth"])
async def logout(response: Response) -> MessageResponse:
    response.delete_cookie("access_token")
    return MessageResponse(message="Successfully logged out")
