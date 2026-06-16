"""
Authentication API routes for AutoAgentHire.

Endpoints
---------
POST /auth/signup   – Register a new user
POST /auth/login    – Authenticate and receive a JWT
GET  /auth/me       – Return the current authenticated user's profile
POST /auth/google   – Sign in / register with a Google ID token
"""

import os
import uuid as _uuid
import requests as http_requests
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.auth.password import hash_password, verify_password
from backend.auth.jwt import create_access_token
from backend.auth.validators import validate_email_format, validate_password_strength, validate_phone_number
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.crud import UserRepository
from backend.database.models_complete import User

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None


class SignupResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    id: int
    uuid: str
    email: str
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime | None = None
    last_login: datetime | None = None

    class Config:
        from_attributes = True


class GoogleAuthRequest(BaseModel):
    access_token: str = Field(..., description="Google OAuth2 access token from useGoogleLogin")


# ── Signup ────────────────────────────────────────────────────────────────────

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """Create a new user account.

    1. Validate email format (backend re-check).
    2. Validate password strength.
    3. Ensure email is not already registered.
    4. Hash password with bcrypt and persist the user.
    """

    # 1. Email format (pydantic already validates via EmailStr, but we add our own)
    email_err = validate_email_format(body.email)
    if email_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=email_err)

    # 2. Password strength
    pw_err = validate_password_strength(body.password)
    if pw_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_err)

    # 3. Phone validation (if provided)
    if body.phone:
        phone_err = validate_phone_number(body.phone)
        if phone_err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=phone_err)

    # 4. Duplicate check
    existing = UserRepository.get_by_email(db, email=body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists. Please login.",
        )

    # 5. Hash + store
    hashed = hash_password(body.password)
    try:
        UserRepository.create(
            db,
            email=body.email,
            hashed_password=hashed,
            full_name=body.full_name or "",
            phone=body.phone,
            location=body.location,
        )
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).error("DB insert failed during signup: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account. Please try again.",
        )

    import logging as _logging
    _logging.getLogger(__name__).info("User profile saved successfully: %s", body.email)
    return SignupResponse(message="User created successfully")


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and get JWT token",
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token.

    Algorithm
    ---------
    1. Validate email format.
    2. Look up user by email.
    3. If not found → 401 "Invalid credentials. Please sign up first."
    4. Compare password with stored hash via bcrypt.
    5. If mismatch → 401 "Incorrect password."
    6. On success → issue JWT with ``sub=email``.
    """

    # 1. Email format
    email_err = validate_email_format(body.email)
    if email_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=email_err)

    # 2. Look up user
    user = UserRepository.get_by_email(db, email=body.email)

    import logging as _logging
    _log = _logging.getLogger(__name__)

    # 3. Auto-create account if user does NOT exist
    if user is None:
        _log.info("User not found for %s — auto-creating account", body.email)
        hashed = hash_password(body.password)
        try:
            user = UserRepository.create(
                db,
                email=body.email,
                hashed_password=hashed,
                full_name="",
            )
        except Exception as exc:
            _log.error("DB insert failed during auto-signup: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account. Please try again.",
            )
        _log.info("User profile saved successfully (auto-signup): %s", body.email)
    else:
        # 4-5. Existing user — verify password
        if not verify_password(body.password, str(user.hashed_password)):  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password.",
            )

    # Update last_login timestamp
    try:
        UserRepository.update(db, int(user.id), last_login=datetime.now(timezone.utc))  # type: ignore
    except Exception:
        pass  # non-critical – don't fail the login

    # 6. Issue token
    access_token = create_access_token(data={"sub": user.email})
    return LoginResponse(access_token=access_token)


# ── Current user profile ─────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.post(
    "/google",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Sign in or register with Google",
)
def google_auth(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Verify a Google OAuth2 access token, then sign in or auto-register the user.

    Flow
    ----
    1. Call Google's userinfo endpoint with the access token to verify it.
    2. Extract email + name from the verified payload.
    3. Find or create the user in the database.
    4. Return our own JWT access token.
    """
    # 1. Verify token by calling Google's userinfo endpoint
    try:
        resp = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {body.access_token}"},
            timeout=10,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach Google servers: {exc}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google access token.",
        )

    userinfo = resp.json()
    google_email: str = userinfo.get("email", "")
    google_name: str = userinfo.get("name", "")
    email_verified: bool = userinfo.get("email_verified", False)

    if not google_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email address.",
        )
    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email is not verified.",
        )

    # 2. Find or create user
    user = UserRepository.get_by_email(db, email=google_email)
    if user is None:
        # Auto-register: generate a random secure password (the user won't use it)
        random_pw = hash_password(_uuid.uuid4().hex + _uuid.uuid4().hex)
        user = UserRepository.create(
            db,
            email=google_email,
            hashed_password=random_pw,
            full_name=google_name,
        )

    # 3. Update last_login
    try:
        UserRepository.update(db, int(user.id), last_login=datetime.now(timezone.utc))  # type: ignore
    except Exception:
        pass

    # 4. Issue our JWT
    access_token = create_access_token(data={"sub": user.email})
    return LoginResponse(access_token=access_token)
@router.post('/token', include_in_schema=False)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = UserRepository.get_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, str(user.hashed_password)):
        raise HTTPException(status_code=401, detail='Incorrect email or password')
    access_token = create_access_token(data={'sub': user.email})
    return {'access_token': access_token, 'token_type': 'bearer'}
