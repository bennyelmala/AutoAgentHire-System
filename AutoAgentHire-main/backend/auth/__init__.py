"""
Authentication module for AutoAgentHire.
Provides password hashing, JWT tokens, validation, and FastAPI dependencies.
"""

from backend.auth.password import hash_password, verify_password
from backend.auth.jwt import create_access_token, decode_access_token
from backend.auth.validators import validate_email_format, validate_password_strength
from backend.auth.dependencies import get_current_user

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "validate_email_format",
    "validate_password_strength",
    "get_current_user",
]
