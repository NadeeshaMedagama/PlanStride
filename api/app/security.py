import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

# JWT audiences scope a token to the surface it was issued for. A token minted
# for one surface fails audience validation on another, so an app session
# cannot be replayed against the internal API (or vice versa) even for an admin.
JWT_AUDIENCE_APP = "app"
JWT_AUDIENCE_INTERNAL = "internal"

# Initialize Argon2 password hasher with secure defaults
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using Argon2."""
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False


# Verified against when no account matches a login attempt, so an unknown email
# costs the same Argon2 work as a wrong password and response time doesn't
# reveal which emails have accounts.
_TIMING_EQUALIZER_HASH = ph.hash(secrets.token_urlsafe(16))


def burn_password_check(plain_password: str) -> None:
    verify_password(plain_password, _TIMING_EQUALIZER_HASH)


def generate_invite_token() -> str:
    """A URL-safe, unguessable token for an invite link (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    """Invites are looked up by this hash; the raw token is never stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_jwt_token(data: dict, audience: str) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "aud": audience})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
