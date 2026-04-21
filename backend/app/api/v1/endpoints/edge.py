"""Edge/control gateway endpoints for on-prem <-> SaaS synchronization."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.base import get_db
from app.models import Gateway, LicenseKey, Tenant, Ticket, TicketMessage
from app.services.license_key_service import get_active_license_key_by_code
from app.services.license_service import tenant_license_codes
from app.services.mirror_tenant_service import EDGE_BOT_USERNAME, ensure_edge_bot_user, ensure_mirror_tenant
from app.services.mtls_guard import require_mtls_request
from app.services.ticket_ai_service import analyze_ticket_with_ai
from app.services.token_service import create_gateway_token

router = APIRouter(prefix="/edge", tags=["edge"])


class EdgeRegisterPayload(BaseModel):
    license_key: str
    tenant_slug: str
    instance_name: str = "onprem"
    public_endpoint: Optional[str] = None


class EdgeTicketPayload(BaseModel):
    title: str
    severity: str = "medium"
    category: str = "platform"
    description: str
    environment: Optional[str] = None
    service_name: Optional[str] = None
    attachments: list[dict] = Field(default_factory=list)


async def verify_gateway_by_token(
    authorization: Optional[str],
    db: AsyncSession,
) -> Gateway:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token_value = authorization.replace("Bearer ", "").strip()
    result = await db.execute(select(Gateway).where(Gateway.token == token_value))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=401, detail="Invalid gateway token")
    return gateway


@router.post("/register")
async def register_onprem_instance(
    payload: EdgeRegisterPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Register an on-prem installation against a SaaS tenant using a commercial license key.

    Returns a control gateway token (bound to the mirror tenant) to:
    - bootstrap mTLS via /api/v1/agents/bootstrap/mtls
    - send self-monitoring telemetry to the mirror tenant
    - open auto-tickets when required
    """

    key = (payload.license_key or "").strip()
    tenant_slug = re.sub(r"[^a-z0-9-]", "-", (payload.tenant_slug or "").lower()).strip("-")
    if not key or not tenant_slug:
        raise HTTPException(status_code=400, detail="license_key and tenant_slug are required")

    license_record = await get_active_license_key_by_code(db=db, code=key)
    if not license_record:
        raise HTTPException(status_code=403, detail="Invalid or expired license key")
    if not license_record.tenant_id:
        raise HTTPException(status_code=409, detail="License key is not bound to any tenant yet")

    customer = await db.get(Tenant, license_record.tenant_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tenant not found")

    mirror = await ensure_mirror_tenant(db, customer)

    # Create (or reuse) a control gateway token for the mirror tenant.
    gateway_name = f"Control Gateway {payload.instance_name}".strip()
    gateway_config = {
        "edge_control": True,
        "provisioning_source": "edge_register",
        "customer_tenant_id": customer.id,
        "customer_tenant_slug": customer.slug,
        "license_key_id": license_record.id,
        "public_endpoint": payload.public_endpoint,
    }
    gateway = await create_gateway_token(
        db=db,
        tenant_id=mirror.id,
        name=gateway_name,
        gateway_type="control",
        host=payload.public_endpoint or "onprem",
        port=9443,
        config=gateway_config,
        reuse_pending=True,
    )
    gateway.config = {**(gateway.config or {}), **gateway_config}
    flag_modified(gateway, "config")
    await db.commit()

    licenses = tenant_license_codes(customer)
    entitlements = dict(license_record.entitlements or {})
    # Ensure the local tenant always has "infra" and "included".
    entitlements.setdefault("infra", True)
    entitlements.setdefault("included", True)
    # Provide the resolved license set (plan/settings + key entitlements).
    resolved_licenses = sorted(set(licenses) | {code for code, enabled in entitlements.items() if enabled})

    return {
        "status": "registered",
        "customer_tenant": {"id": customer.id, "slug": customer.slug, "name": customer.name},
        "mirror_tenant": {"id": mirror.id, "slug": mirror.slug, "name": mirror.name},
        "control_gateway": {
            "id": gateway.id,
            "token": gateway.token,
        },
        "bootstrap": {
            "platform_url": settings.PLATFORM_URL,
            "bootstrap_path": "/api/v1/agents/bootstrap/mtls",
            "mtls_platform_url": settings.MTLS_PLATFORM_URL,
        },
        "license": {
            "edition": license_record.edition,
            "expires_at": license_record.expires_at,
            "licenses": resolved_licenses,
            "limits": license_record.limits or {},
        },
        "sync": {"poll_seconds": 300},
    }


@router.get("/sync")
async def edge_sync(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Periodic sync endpoint used by the control gateway.
    Requires mTLS and a gateway token issued for the mirror tenant.
    """
    require_mtls_request(request)
    gateway = await verify_gateway_by_token(authorization, db)
    cfg = gateway.config or {}
    if gateway.type != "control" and not cfg.get("edge_control"):
        raise HTTPException(status_code=403, detail="Edge control gateway token required")

    customer_tenant_id = cfg.get("customer_tenant_id")
    license_key_id = cfg.get("license_key_id")
    customer = await db.get(Tenant, customer_tenant_id) if customer_tenant_id else None
    license_record = await db.get(LicenseKey, license_key_id) if license_key_id else None

    resolved = sorted(tenant_license_codes(customer) if customer else [])
    entitlements = dict((license_record.entitlements or {}) if license_record else {})
    entitlements.setdefault("infra", True)
    entitlements.setdefault("included", True)
    resolved = sorted(set(resolved) | {code for code, enabled in entitlements.items() if enabled})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_tenant": {"id": customer.id, "slug": customer.slug, "name": customer.name} if customer else None,
        "license": {
            "expires_at": license_record.expires_at if license_record else None,
            "status": license_record.status if license_record else None,
            "licenses": resolved,
            "limits": (license_record.limits or {}) if license_record else {},
        },
        "updates": {
            "check_url": f"{settings.MTLS_PLATFORM_URL.rstrip('/')}/api/v1/agents/updates/check",
            "notes": "Control gateway should check agent/gateway updates and mirror artifacts locally when needed.",
        },
        "poll_seconds": 300,
    }


@router.post("/tickets")
async def edge_create_ticket(
    request: Request,
    payload: EdgeTicketPayload,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a ticket on behalf of an on-prem installation.
    Requires mTLS + edge control gateway token.
    """
    require_mtls_request(request)
    gateway = await verify_gateway_by_token(authorization, db)
    cfg = gateway.config or {}
    if gateway.type != "control" and not cfg.get("edge_control"):
        raise HTTPException(status_code=403, detail="Edge control gateway token required")

    bot = await ensure_edge_bot_user(db, gateway.tenant_id)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        tenant_id=gateway.tenant_id,
        created_by=bot.id,
        title=payload.title,
        category=payload.category,
        severity=payload.severity,
        environment=payload.environment,
        service_name=payload.service_name,
        description=payload.description,
        status="open",
        source="edge",
    )
    db.add(ticket)
    db.add(
        TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            tenant_id=gateway.tenant_id,
            author_id=bot.id,
            author_role="edge",
            message=payload.description,
            is_internal=False,
            attachments=payload.attachments,
        )
    )
    await db.flush()

    ai_result = await analyze_ticket_with_ai(
        {
            "title": payload.title,
            "category": payload.category,
            "severity": payload.severity,
            "environment": payload.environment,
            "service_name": payload.service_name,
            "description": payload.description,
            "attachments": payload.attachments,
        }
    )
    ticket.ai_status = ai_result.get("status", "failed")
    ticket.ai_summary = ai_result.get("summary")
    ticket.ai_suspected_cause = ai_result.get("suspected_cause")
    ticket.ai_recommended_actions = ai_result.get("recommended_actions")
    ticket.ai_confidence = ai_result.get("confidence", 0)
    ticket.ai_model = ai_result.get("model")
    ticket.ai_payload = ai_result
    if ticket.ai_status == "completed":
        ticket.status = "triaged"

    await db.commit()
    return {"status": "created", "ticket_id": ticket.id, "ai_status": ticket.ai_status}
