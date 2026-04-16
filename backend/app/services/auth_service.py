"""Authentication helpers for password hashing and verification."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    # Backward-compatible fallback for legacy plain-text seeded rows.
    if not stored_password.startswith("$"):
        return plain_password == stored_password

    return pwd_context.verify(plain_password, stored_password)


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
    
    to_encode.update({"exp": expire, "type": token_type})
    
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
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")
