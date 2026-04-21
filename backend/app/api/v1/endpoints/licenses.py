"""Licensing endpoints for SaaS and on-prem installations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import LicenseKey, Tenant, User
from app.services.license_key_service import create_license_key, get_active_license_key_by_code
from app.services.license_service import AGENT_MODULE_CATALOG, AGENT_PROFILES, PLAN_LICENSES, tenant_license_codes

router = APIRouter(prefix="/licenses", tags=["licenses"])


def require_superadmin(user: User) -> None:
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin role required")


class LicenseKeyCreatePayload(BaseModel):
    tenant_id: Optional[str] = Field(None, description="Customer tenant id to bind the key")
    edition: str = Field("saas", description="saas|onprem")
    entitlements: dict = Field(default_factory=dict)
    limits: dict = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class LicenseActivatePayload(BaseModel):
    license_key: str


@router.get("/catalog")
async def license_catalog(user: User = Depends(get_current_user)):
    """Public catalog (requires login) to show license codes and what they unlock."""
    profiles = [
        {
            "key": key,
            "label": value.get("label"),
            "description": value.get("description"),
            "required_license": value.get("license"),
        }
        for key, value in AGENT_PROFILES.items()
    ]
    modules = [
        {
            "key": key,
            "label": value.get("label"),
            "required_license": value.get("license"),
        }
        for key, value in AGENT_MODULE_CATALOG.items()
    ]
    return {
        "plan_licenses": {plan: sorted(list(codes)) for plan, codes in PLAN_LICENSES.items()},
        "agent_profiles": profiles,
        "agent_modules": modules,
        "license_codes": sorted(
            list({m.get("license") for m in AGENT_MODULE_CATALOG.values() if m.get("license")} | {"infra", "included"})
        ),
    }


@router.get("/status")
async def tenant_license_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    licenses = tenant_license_codes(tenant)
    return {
        "tenant_id": tenant.id,
        "tenant_slug": tenant.slug,
        "plan": str(tenant.plan).replace("PlanType.", ""),
        "licenses": sorted(licenses),
        "license_key": bool(tenant.license_key),
        "license_expires_at": tenant.license_expires_at,
    }


@router.post("/activate")
async def activate_license_key(
    payload: LicenseActivatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """On-prem friendly: allow tenant admin to register a license key locally."""
    if user.role not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Administrator role required")
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    key = payload.license_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="license_key required")
    # If this installation has a local LicenseKey registry, validate it here.
    local = await get_active_license_key_by_code(db=db, code=key)
    tenant.license_key = key
    if local and local.expires_at:
        tenant.license_expires_at = local.expires_at.astimezone(timezone.utc).isoformat()
    await db.commit()
    return {"status": "activated"}


@router.get("/keys")
async def list_license_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    result = await db.execute(select(LicenseKey).order_by(desc(LicenseKey.created_at)).limit(200))
    items = result.scalars().all()
    return [
        {
            "id": item.id,
            "code": item.code,
            "tenant_id": item.tenant_id,
            "edition": item.edition,
            "status": item.status,
            "expires_at": item.expires_at,
            "entitlements": item.entitlements or {},
            "limits": item.limits or {},
        }
        for item in items
    ]


@router.post("/keys")
async def create_license_key_admin(
    payload: LicenseKeyCreatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    if payload.tenant_id:
        tenant = await db.get(Tenant, payload.tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
    key = await create_license_key(
        db=db,
        tenant_id=payload.tenant_id,
        edition=payload.edition,
        entitlements=payload.entitlements,
        limits=payload.limits,
        expires_at=payload.expires_at,
    )
    return {"status": "created", "license_id": key.id, "code": key.code}

