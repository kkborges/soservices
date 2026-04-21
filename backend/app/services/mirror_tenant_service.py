from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, User
from app.services.auth_service import hash_password


EDGE_BOT_USERNAME = "edge_bot@las.local"
EDGE_BOT_NAME = "LAS Edge Bot"


def mirror_slug(customer_slug: str) -> str:
    base = (customer_slug or "").strip().lower()
    if not base:
        return "unknown-0"
    if base.endswith("-0"):
        return base
    return f"{base}-0"


async def ensure_edge_bot_user(db: AsyncSession, tenant_id: str) -> User:
    result = await db.execute(select(User).where(User.tenant_id == tenant_id, User.username == EDGE_BOT_USERNAME))
    user = result.scalar_one_or_none()
    if user:
        user.active = True
        user.role = "admin"
        user.full_name = EDGE_BOT_NAME
        await db.commit()
        return user
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        username=EDGE_BOT_USERNAME,
        email=EDGE_BOT_USERNAME,
        full_name=EDGE_BOT_NAME,
        password_hash=hash_password(str(uuid.uuid4())),
        role="admin",
        active=True,
        must_change_password=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def ensure_mirror_tenant(db: AsyncSession, customer: Tenant) -> Tenant:
    """
    Ensure the SaaS mirror tenant exists for a given customer tenant.

    The mirror tenant is internal and used to monitor the LAS platform itself
    and on-prem environments related to that customer.
    """

    if not customer or not customer.slug:
        raise ValueError("customer tenant missing slug")

    target_slug = mirror_slug(customer.slug)
    result = await db.execute(select(Tenant).where(Tenant.slug == target_slug))
    mirror = result.scalar_one_or_none()

    base_settings = {
        "internal_platform": True,
        "hidden_from_customers": True,
        "mirror_of": customer.id,
        "mirror_of_slug": customer.slug,
        "company_name": "LAS",
        "platform_name": "LAS Plataforma de Monitoramento e Observabilidade",
    }
    if mirror:
        merged = dict(mirror.settings or {})
        merged.update(base_settings)
        mirror.settings = merged
        mirror.status = "active"
        mirror.plan = "enterprise"
        await db.commit()
        await ensure_edge_bot_user(db, mirror.id)
        return mirror

    mirror = Tenant(
        id=str(uuid.uuid4()),
        name=f"{customer.name} - Observabilidade LAS",
        slug=target_slug,
        admin_email=customer.admin_email,
        admin_name=customer.admin_name,
        plan="enterprise",
        status="active",
        max_hosts=5000,
        max_agents=5000,
        max_users=200,
        features={
            "agents": True,
            "gateways": True,
            "otel": True,
            "logs": True,
            "alerts": True,
            "network_discovery": True,
            "snmp": True,
            "security": True,
        },
        settings=base_settings,
    )
    db.add(mirror)
    await db.flush()
    await db.commit()
    await db.refresh(mirror)
    await ensure_edge_bot_user(db, mirror.id)
    return mirror

