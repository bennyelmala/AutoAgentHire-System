"""
Password hashing utilities using bcrypt via passlib.
Never store plain-text passwords – always hash before persisting.
"""

from passlib.context import CryptContext

# bcrypt is the recommended scheme for password hashing.
# "deprecated='auto'" means any future scheme change auto-rehashes on verify.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        plain_password: The raw password entered by the user.

    Returns:
        A bcrypt hash string suitable for database storage.
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain_password: The raw password entered by the user.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return _pwd_context.verify(plain_password, hashed_password)
