"""
JWT (JSON Web Token) utilities for access-token creation and verification.
Uses python-jose with the HS256 algorithm by default.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt

# ---------------------------------------------------------------------------
# These values are imported at module level from config so every call uses the
# same settings.  If config import fails (e.g. during isolated unit tests),
# sensible defaults are provided.
# ---------------------------------------------------------------------------
try:
    from config import settings

    SECRET_KEY: str = settings.SECRET_KEY
    ALGORITHM: str = settings.ALGORITHM  # default "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES  # default 30
except Exception:
    import os

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload to encode (must include ``sub`` – typically the user email).
        expires_delta: Custom expiry duration.  Falls back to
            ``ACCESS_TOKEN_EXPIRE_MINUTES`` from settings.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
