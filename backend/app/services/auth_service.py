"""Authentication helpers for password hashing and verification."""
from passlib.context import CryptContext


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
