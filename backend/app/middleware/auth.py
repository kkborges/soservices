"""Session and bearer auth middleware for FastAPI."""
from types import SimpleNamespace
from typing import Optional

from fastapi import Depends, HTTPException, Cookie, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.db.base import get_db
from app.models import Session, User
from app.services.auth_service import decode_token


async def get_current_user(
    las_session: Optional[str] = Cookie(None, alias="las_session"),
    nexus_session: Optional[str] = Cookie(None, alias="nexus_session"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    session_token = (las_session or nexus_session or "").strip() or None

    if not session_token and authorization and authorization.startswith("Bearer "):
        payload = decode_token(authorization.replace("Bearer ", "", 1).strip())
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        user = await db.get(User, user_id) if user_id else None
        if user and user.active:
            user.tenant_id = tenant_id or user.tenant_id
            return user
        if user_id and tenant_id:
            return SimpleNamespace(
                id=user_id,
                tenant_id=tenant_id,
                username=payload.get("username") or user_id,
                role=payload.get("role") or "admin",
                active=True,
            )

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(Session).where(
            Session.token == session_token,
            Session.active == True,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = await db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User inactive")

    # Attach tenant_id to user object for convenience
    user.tenant_id = session.tenant_id
    return user
