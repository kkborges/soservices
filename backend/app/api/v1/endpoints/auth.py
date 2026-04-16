"""Authentication endpoints for session-backed UI/API access."""
from datetime import datetime, timedelta, timezone
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import Session, Tenant, User
from app.services.auth_service import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    resolved_username = None
    resolved_password = None

    if "application/json" in content_type:
        payload = LoginPayload.model_validate(await request.json())
        resolved_username = payload.username
        resolved_password = payload.password
    else:
        form = await request.form()
        resolved_username = form.get("username")
        resolved_password = form.get("password")

    if not resolved_username or not resolved_password:
        raise HTTPException(status_code=422, detail="Username and password are required")

    result = await db.execute(select(User).where(User.username == resolved_username))
    candidates = result.scalars().all()
    user = next((item for item in candidates if item.role == "superadmin" and item.active), None)
    if not user:
        user = next((item for item in candidates if item.active), None)
    if not user or not user.active or not verify_password(resolved_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session = Session(
        id=str(uuid4()),
        token=secrets.token_urlsafe(32),
        user_id=user.id,
        tenant_id=user.tenant_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        last_activity=datetime.now(timezone.utc),
        active=True,
    )
    db.add(session)
    await db.commit()

    response.set_cookie(
        key="nexus_session",
        value=session.token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 60 * 60,
    )

    tenant = await db.get(Tenant, user.tenant_id)
    return {
        "status": "ok",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "scope": "platform" if user.role == "superadmin" else "tenant",
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.name if tenant else None,
        },
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("nexus_session")
    return {"status": "ok"}


@router.get("/bootstrap")
async def bootstrap(db: AsyncSession = Depends(get_db)):
    tenant_result = await db.execute(select(Tenant).limit(1))
    tenant = tenant_result.scalar_one_or_none()

    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()

    return {
        "has_tenant": tenant is not None,
        "has_user": user is not None,
        "app_name": "LAS Plataforma de Monitoramento e Observabilidade",
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
        } if tenant else None,
        "user_hint": {
            "username": user.username,
            "role": user.role,
            "scope": "platform" if user.role == "superadmin" else "tenant",
        } if user else None,
    }


@router.get("/me")
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, current_user.tenant_id)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "scope": "platform" if current_user.role == "superadmin" else "tenant",
        "must_change_password": current_user.must_change_password,
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
        } if tenant else None,
    }
