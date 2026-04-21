"""Shared FastAPI dependency aliases."""

from app.db.base import get_db
from app.middleware.auth import get_current_user

__all__ = ["get_db", "get_current_user"]

