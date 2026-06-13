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
from app.services.license_service import (
    AGENT_MODULE_CATALOG,
    AGENT_PROFILES,
    LICENSE_BILLING_UNIT_CATALOG,
    LICENSE_PACKAGE_CATALOG,
    PLAN_LICENSES,
    merge_billing_config,
    tenant_license_codes,
)

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


class BillingUnitConfigPayload(BaseModel):
    enabled: bool = True
    price_per_unit: float = 0
    included_units: float = 0
    overage_price: float = 0
    unit_label: Optional[str] = None
    notes: Optional[str] = None


class BillingConfigPayload(BaseModel):
    currency: str = "BRL"
    billing_cycle: str = "monthly"
    notes: Optional[str] = None
    units: dict[str, BillingUnitConfigPayload] = Field(default_factory=dict)
    packages: dict[str, dict] = Field(default_factory=dict)
    discounts: dict[str, float] = Field(default_factory=dict)


async def get_platform_settings_tenant(db: AsyncSession) -> Tenant:
    tenants = (await db.execute(select(Tenant).order_by(Tenant.name))).scalars().all()
    tenant = next((item for item in tenants if (item.settings or {}).get("internal_platform")), None)
    tenant = tenant or (tenants[0] if tenants else None)
    if not tenant:
        raise HTTPException(status_code=404, detail="Platform tenant not found")
    return tenant


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
        "billing_units": [
            {"code": code, **spec}
            for code, spec in LICENSE_BILLING_UNIT_CATALOG.items()
        ],
        "billing_packages": [
            {"code": code, **spec}
            for code, spec in LICENSE_PACKAGE_CATALOG.items()
        ],
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


@router.get("/admin/billing-config")
async def get_billing_config_admin(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    tenant = await get_platform_settings_tenant(db)
    settings = tenant.settings or {}
    config = merge_billing_config(settings.get("license_billing"))
    return {
        "tenant_id": tenant.id,
        "currency": config["currency"],
        "billing_cycle": config["billing_cycle"],
        "notes": config["notes"],
        "units": [
            {
                "code": code,
                **LICENSE_BILLING_UNIT_CATALOG[code],
                **config["units"][code],
            }
            for code in LICENSE_BILLING_UNIT_CATALOG
        ],
        "packages": [
            {
                "code": code,
                **LICENSE_PACKAGE_CATALOG[code],
                **config["packages"][code],
            }
            for code in LICENSE_PACKAGE_CATALOG
        ],
        "discounts": config["discounts"],
    }


@router.put("/admin/billing-config")
@router.patch("/admin/billing-config")
async def save_billing_config_admin(
    payload: BillingConfigPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    tenant = await get_platform_settings_tenant(db)
    current_settings = dict(tenant.settings or {})
    config_input = {
        "currency": payload.currency,
        "billing_cycle": payload.billing_cycle,
        "notes": payload.notes or "",
        "units": {code: item.model_dump() for code, item in payload.units.items()},
        "packages": payload.packages,
        "discounts": payload.discounts,
    }
    current_settings["license_billing"] = merge_billing_config(config_input)
    tenant.settings = current_settings
    await db.commit()
    return {"status": "saved"}
