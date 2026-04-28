"""Public trial signup endpoints."""
from __future__ import annotations

import re
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.models import LicenseKey, Tenant, User
from app.services.auth_service import hash_password
from app.services.license_key_service import generate_license_code
from app.services.license_service import PLAN_LICENSES
from app.services.mirror_tenant_service import ensure_mirror_tenant

router = APIRouter(prefix="/trial", tags=["trial"])


class TrialSignupPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)
    cnpj: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=60)
    requested_features: list[str] = Field(default_factory=list)
    tenant_slug: str | None = Field(default=None, min_length=2, max_length=80)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:80].strip("-") or f"trial-{uuid.uuid4().hex[:8]}"


def _tenant_url(slug: str) -> str:
    parsed = urlparse(settings.PUBLIC_WEB_URL)
    scheme = parsed.scheme or "https"
    host = parsed.netloc or parsed.path or "las.soservices.com.br"
    return f"{scheme}://{slug}.{host}"


def _send_trial_email(email: str, full_name: str, tenant_url: str, username: str) -> bool:
    if not settings.SMTP_HOST:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Seu trial LAS esta pronto"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = email
    msg.set_content(
        "\n".join(
            [
                f"Ola, {full_name}.",
                "",
                "Seu tenant trial da LAS Plataforma de Monitoramento e Observabilidade foi criado.",
                f"Acesso: {tenant_url}",
                f"Usuario: {username}",
                "",
                "A senha e a que voce cadastrou no formulario trial.",
                f"O periodo trial e de {settings.TRIAL_DAYS} dias com funcionalidades completas habilitadas.",
            ]
        )
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        if settings.SMTP_TLS:
            smtp.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
    return True


@router.post("/signup", status_code=201)
async def create_trial_tenant(payload: TrialSignupPayload, db: AsyncSession = Depends(get_db)):
    """Create a full SaaS trial tenant from a public signup form."""
    slug = _slugify(payload.tenant_slug or payload.company_name)
    username = str(payload.email).lower()
    email = username

    existing = await db.execute(
        select(Tenant).where(or_(Tenant.slug == slug, Tenant.admin_email == email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant slug or admin email already exists")

    trial_days = max(1, int(settings.TRIAL_DAYS or 15))
    trial_expires_at = datetime.now(timezone.utc) + timedelta(days=trial_days)
    licenses = {code: True for code in PLAN_LICENSES["trial"]}
    license_code = generate_license_code(prefix="lastrial")
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.company_name,
        slug=slug,
        plan="trial",
        status="active",
        admin_name=payload.full_name,
        admin_email=email,
        max_hosts=100,
        max_agents=100,
        max_users=10,
        max_synthetic_tests=20,
        license_key=license_code,
        license_expires_at=trial_expires_at.isoformat(),
        features={
            "agents": True,
            "gateways": True,
            "otel": True,
            "logs": True,
            "alerts": True,
            "network_discovery": True,
            "snmp": True,
            "rum": True,
            "synthetics": True,
            "extensions": True,
            "security": True,
            "licenses": licenses,
        },
        settings={
            "company_name": payload.company_name,
            "cnpj": payload.cnpj,
            "phone": payload.phone,
            "requested_features": payload.requested_features,
            "platform_name": "LAS Plataforma de Monitoramento e Observabilidade",
            "trial": True,
            "tenant_url": _tenant_url(slug),
            "licenses": licenses,
        },
    )
    db.add(tenant)
    await db.flush()

    admin_user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        username=username,
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="admin",
        active=True,
        must_change_password=False,
    )
    db.add(admin_user)

    license_key = LicenseKey(
        id=str(uuid.uuid4()),
        code=license_code,
        tenant_id=tenant.id,
        edition="saas-trial",
        status="active",
        expires_at=trial_expires_at,
        entitlements=licenses,
        limits={
            "trial_days": trial_days,
            "max_hosts": tenant.max_hosts,
            "max_agents": tenant.max_agents,
            "max_users": tenant.max_users,
            "max_synthetic_tests": tenant.max_synthetic_tests,
        },
    )
    db.add(license_key)
    await ensure_mirror_tenant(db, tenant)
    await db.commit()

    email_sent = False
    try:
        email_sent = _send_trial_email(email, payload.full_name, _tenant_url(slug), username)
    except Exception:
        email_sent = False

    return {
        "status": "created",
        "tenant_id": tenant.id,
        "tenant_slug": slug,
        "tenant_url": _tenant_url(slug),
        "username": username,
        "trial_expires_at": trial_expires_at.isoformat(),
        "license_key": license_code,
        "email_sent": email_sent,
        "dns_note": "Create wildcard DNS *.las.soservices.com.br or an explicit record for the tenant slug.",
    }
