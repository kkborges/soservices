from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LicenseKey


def generate_license_code(prefix: str = "laslic", length: int = 44) -> str:
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{random_part}"


async def create_license_key(
    *,
    db: AsyncSession,
    tenant_id: Optional[str],
    edition: str = "saas",
    entitlements: Optional[dict] = None,
    limits: Optional[dict] = None,
    expires_at=None,
) -> LicenseKey:
    code = generate_license_code()
    license_key = LicenseKey(
        code=code,
        tenant_id=tenant_id,
        edition=edition,
        status="active",
        entitlements=entitlements or {},
        limits=limits or {},
        expires_at=expires_at,
    )
    db.add(license_key)
    await db.commit()
    await db.refresh(license_key)
    return license_key


async def get_active_license_key_by_code(
    *, db: AsyncSession, code: str
) -> LicenseKey | None:
    if not code:
        return None
    result = await db.execute(select(LicenseKey).where(LicenseKey.code == code))
    license_key = result.scalar_one_or_none()
    if not license_key:
        return None
    if (license_key.status or "active") != "active":
        return None
    if license_key.expires_at and license_key.expires_at < datetime.now(timezone.utc):
        license_key.status = "expired"
        await db.commit()
        return None
    return license_key

