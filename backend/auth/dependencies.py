"""
FastAPI dependencies for authentication.
Provides ``get_current_user`` which extracts and validates the JWT
from the ``Authorization: Bearer <token>`` header.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from backend.auth.jwt import decode_access_token
from backend.database.connection import get_db
from backend.database.models_complete import User
from backend.database.crud import UserRepository

# The tokenUrl points at the login endpoint so Swagger UI can use it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT and return the associated ``User`` row.

    Raises:
        HTTPException 401: If the token is missing, invalid, expired, or the
            user no longer exists / is inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = UserRepository.get_by_email(db, email=email)
    if user is None:
        raise credentials_exception
        
    if not user.is_active:  # type: ignore
        raise credentials_exception

    return user
