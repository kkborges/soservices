"""Authentication helpers for password hashing and verification."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import jwt
import bcrypt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import get_settings

legacy_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Generate a salted password hash suitable for secure storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_password_hash(password: str) -> str:
    """Backward-compatible alias used by tests and older authentication code."""
    return hash_password(password)


def verify_password(plain_password: str, stored_password: str) -> bool:
    """Verify a plain password against a stored hash or legacy seeded password."""
    if not stored_password:
        return False

    # Backward-compatible fallback for legacy plain-text seeded rows.
    if stored_password.startswith("$2"):
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_password.encode("utf-8"))
    if stored_password.startswith("$pbkdf2"):
        return legacy_pwd_context.verify(plain_password, stored_password)
    if not stored_password.startswith("$"):
        return plain_password == stored_password

    return False


async def authenticate_user(db: Any, username: str, password: str) -> Any | None:
    """Authenticate a local user by username and password, returning the user when valid."""
    from sqlalchemy import select

    from app.models import User

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not getattr(user, "active", False):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access",
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing token claims
        expires_delta: Optional custom expiration time
        token_type: Token type ("access" or "refresh")
    
    Returns:
        Encoded JWT token
    """
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "jti": str(uuid4()), "type": token_type})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
        
    Raises:
        jwt.InvalidTokenError: If token is invalid or expired
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
