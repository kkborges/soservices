"""Management endpoints for tenants, discovery, SNMP, tasks, alerts and integrations."""
from __future__ import annotations

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Alert,
    AlertRule,
    Extension,
    ExtensionConfig,
    Gateway,
    Host,
    HostMetric,
    IdsAlert,
    LogEntry,
    NetworkAsset,
    OtelTrace,
    RumEvent,
    SecurityEvent,
    Session,
    SyntheticTest,
    Task,
    Tenant,
    User,
)
from app.services.auth_service import hash_password
from app.services.runtime_monitor import list_instance_metrics
from app.services.gateway_routing import gateway_health
from app.services.runtime_tasks import cancel_runtime_task, launch_runtime_task, run_network_discovery, run_snmp_get, run_snmp_refresh
from app.services.mirror_tenant_service import ensure_mirror_tenant
from app.services.license_service import LICENSE_BILLING_UNIT_CATALOG, merge_billing_config, simulate_billing, tenant_license_codes

router = APIRouter(tags=["management"])
NETWORK_ASSET_TYPES = {"network", "switch", "router", "firewall", "ap", "hub", "access_point", "wifi", "wireless", "printer", "ups"}
DEFAULT_DISCOVERY_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 161, 389, 443, 445, 465, 514, 587, 636,
    993, 995, 1433, 1521, 2049, 2375, 2376, 3000, 3306, 3389, 5000, 5432, 5601, 5672,
    5900, 5985, 5986, 6379, 7001, 7002, 8000, 8080, 8081, 8161, 8443, 8500, 8888, 9000,
    9042, 9092, 9200, 9300, 9418, 9443, 10050, 11211, 15672, 27017, 27018, 27019,
]
PERMISSION_GROUPS = {
    "applications": {"label": "Usuarios Aplicacoes", "role": "operator"},
    "databases": {"label": "Usuarios Bancos de Dados", "role": "operator"},
    "security": {"label": "Usuarios Seguranca", "role": "operator"},
    "administrators": {"label": "Usuarios Administradores", "role": "admin"},
    "networks": {"label": "Usuarios Redes", "role": "operator"},
    "viewer": {"label": "Usuarios Leitura", "role": "viewer"},
}
PERMISSION_VIEWS = {
    "dashboard", "onboarding", "hosts", "processes", "services", "applications", "topologies",
    "dashboards", "databases", "messaging", "orchestration", "synthetics", "network", "security",
    "incidents", "logs", "traces", "gateways", "agents", "tasks", "alerts", "tickets",
    "integrations", "users", "settings",
}


def require_admin(user: User) -> None:
    if user.role not in {"superadmin", "admin"}:
        raise HTTPException(status_code=403, detail="Administrator role required")


def require_superadmin(user: User) -> None:
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin role required")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", (value or "").lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or f"tenant-{uuid.uuid4().hex[:8]}"


def username_from_email_or_name(email: str | None, name: str) -> str:
    if email and "@" in email:
        candidate = email.split("@", 1)[0]
    else:
        candidate = name
    username = re.sub(r"[^a-zA-Z0-9_.-]", "_", (candidate or "").strip()).strip("_.-")
    return username or f"admin_{uuid.uuid4().hex[:8]}"


def normalize_plan(value: str | None) -> str:
    plan = str(value or "enterprise").replace("PlanType.", "").strip().lower()
    aliases = {
        "free": "trial",
        "demo": "trial",
        "professional": "professional",
        "pro": "professional",
        "starter": "starter",
        "enterprise": "enterprise",
        "trial": "trial",
    }
    return aliases.get(plan, "enterprise")


class TenantCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    slug: Optional[str] = None
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_username: Optional[str] = None
    admin_password: str = Field(min_length=4)
    plan: str = "enterprise"

    @model_validator(mode="before")
    @classmethod
    def accept_frontend_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload["name"] = payload.get("name") or payload.get("company_name") or payload.get("tenant_name")
        payload["slug"] = payload.get("slug") or payload.get("tenant_slug")
        payload["admin_name"] = payload.get("admin_name") or payload.get("full_name") or payload.get("name")
        payload["admin_email"] = payload.get("admin_email") or payload.get("email")
        payload["admin_username"] = payload.get("admin_username") or payload.get("username") or payload.get("admin_user")
        payload["admin_password"] = payload.get("admin_password") or payload.get("password") or payload.get("initial_password")
        return payload


class TenantUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    status: str = "active"
    plan: str = "enterprise"


class DiscoveryPayload(BaseModel):
    cidr: str
    ports: list[int] = Field(default_factory=lambda: DEFAULT_DISCOVERY_PORTS.copy())
    timeout_ms: int = 350
    snmp_community: str = "public"
    gateway_id: Optional[str] = None


class SnmpGetPayload(BaseModel):
    ip: str
    oid: str = "1.3.6.1.2.1.1.1.0"
    snmp_community: str = "public"
    snmp_port: int = 161
    gateway_id: Optional[str] = None


class HostConfigPayload(BaseModel):
    monitoring_mode: str = "infra+otel"
    otel_enabled: bool = False
    log_collection: bool = True
    ids_enabled: bool = False
    vuln_scan_enabled: bool = False
    apm_enabled: bool = False
    tags: list[str] = Field(default_factory=list)
    log_paths: list[str] = Field(default_factory=list)


async def select_task_gateway(db: AsyncSession, tenant_id: str, gateway_id: Optional[str] = None) -> Gateway | None:
    query = select(Gateway).where(Gateway.tenant_id == tenant_id, Gateway.status == "online")
    if gateway_id:
        query = query.where(Gateway.id == gateway_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none()

    result = await db.execute(query.order_by(desc(Gateway.last_heartbeat), Gateway.name).limit(20))
    gateways = result.scalars().all()
    for gateway in gateways:
        modules = ((gateway.config or {}).get("last_metadata") or {}).get("modules") or {}
        configured_modules = (gateway.config or {}).get("modules") or {}
        if modules.get("network_discovery") or modules.get("snmp") or configured_modules.get("network_discovery") or configured_modules.get("snmp"):
            return gateway
    for gateway in gateways:
        if gateway.type in {"agents", "infra", "security", "proxy"}:
            return gateway
    return None


class AlertRulePayload(BaseModel):
    name: str
    description: Optional[str] = None
    entity_type: str = "host"
    metric: str
    condition_op: str
    threshold_value: float
    duration_seconds: int = 60
    severity: str = "medium"
    channels: list[str] = Field(default_factory=list)
    use_baseline: bool = False
    enabled: bool = True
    entity_ids: list[str] = Field(default_factory=list)
    tags_filter: list[str] = Field(default_factory=list)
    baseline_sensitivity: float = 3.0
    suppress_seconds: int = 300


class ExtensionConfigPayload(BaseModel):
    extension_slug: str
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class ExtensionInstancePayload(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=255)
    enabled: bool = True
    config: dict = Field(default_factory=dict)
    run_on: str = "auto"  # auto|gateway|server|agent (agent reserved)
    gateway_type: Optional[str] = "integrations"
    interval_seconds: int = 300


class ImpersonatePayload(BaseModel):
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None


@router.get("/platform/tenants")
@router.get("/tenants")
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    result = await db.execute(select(Tenant).order_by(Tenant.name))
    tenants = result.scalars().all()
    return [
        {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "plan": str(tenant.plan),
            "status": tenant.status,
            "admin_name": tenant.admin_name,
            "admin_email": tenant.admin_email,
            "max_hosts": tenant.max_hosts,
            "max_agents": tenant.max_agents,
            "max_users": tenant.max_users,
            "internal": bool((tenant.settings or {}).get("internal_platform")),
        }
        for tenant in tenants
    ]


@router.get("/platform/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    rows = (
        await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .order_by(User.role, User.email)
        )
    ).scalars().all()
    users = [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "username": row.username,
            "email": row.email,
            "name": row.full_name or row.username or row.email,
            "full_name": row.full_name,
            "role": row.role,
            "active": row.active,
            "status": "active" if row.active else "inactive",
            "must_change_password": row.must_change_password,
            "last_login": row.last_login.isoformat() if row.last_login else None,
        }
        for row in rows
    ]
    return {"tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug}, "users": users, "items": users, "results": users}


@router.get("/admin/overview")
@router.get("/platform/stats")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    tenants_result = await db.execute(select(Tenant).order_by(Tenant.name))
    tenants = tenants_result.scalars().all()

    host_count_rows = (
        await db.execute(
            select(
                Host.tenant_id,
                func.count(Host.id),
                func.count(Host.id).filter(or_(Host.otel_enabled == True, Host.apm_enabled == True, Host.monitoring_mode == "infra+otel")),
            ).group_by(Host.tenant_id)
        )
    ).all()
    host_counts = {row[0]: int(row[1] or 0) for row in host_count_rows}
    host_full_counts = {row[0]: int(row[2] or 0) for row in host_count_rows}
    asset_counts = dict(
        (await db.execute(select(NetworkAsset.tenant_id, func.count(NetworkAsset.id)).group_by(NetworkAsset.tenant_id))).all()
    )
    user_counts = dict(
        (await db.execute(select(User.tenant_id, func.count(User.id)).group_by(User.tenant_id))).all()
    )
    synthetic_counts = dict(
        (await db.execute(select(SyntheticTest.tenant_id, func.count(SyntheticTest.id)).group_by(SyntheticTest.tenant_id))).all()
    )
    extension_metric_rows = (
        await db.execute(
            select(ExtensionConfig.tenant_id, func.sum(ExtensionConfig.metrics_collected))
            .group_by(ExtensionConfig.tenant_id)
        )
    ).all()
    extension_metric_units = {row[0]: int((row[1] or 0) // 100) for row in extension_metric_rows}
    snmp_asset_rows = (
        await db.execute(
            select(
                NetworkAsset.tenant_id,
                func.count(NetworkAsset.id).filter(NetworkAsset.snmp_enabled == True),
                func.count(NetworkAsset.id).filter(NetworkAsset.snmp_enabled == False),
            ).group_by(NetworkAsset.tenant_id)
        )
    ).all()
    snmp_asset_counts = {row[0]: int(row[1] or 0) for row in snmp_asset_rows}
    discovered_asset_counts = {row[0]: int(row[2] or 0) for row in snmp_asset_rows}
    trace_rows = (
        await db.execute(
            select(OtelTrace.tenant_id, func.count(OtelTrace.id))
            .group_by(OtelTrace.tenant_id)
        )
    ).all()
    trace_counts = {row[0]: int(row[1] or 0) for row in trace_rows}
    rum_rows = (
        await db.execute(
            select(RumEvent.tenant_id, func.count(RumEvent.id))
            .group_by(RumEvent.tenant_id)
        )
    ).all()
    rum_counts = {row[0]: int(row[1] or 0) for row in rum_rows}
    ids_rows = (
        await db.execute(
            select(IdsAlert.tenant_id, func.count(IdsAlert.id))
            .group_by(IdsAlert.tenant_id)
        )
    ).all()
    ids_counts = {row[0]: int(row[1] or 0) for row in ids_rows}
    security_event_rows = (
        await db.execute(
            select(SecurityEvent.tenant_id, func.count(SecurityEvent.id))
            .group_by(SecurityEvent.tenant_id)
        )
    ).all()
    security_event_counts = {row[0]: int(row[1] or 0) for row in security_event_rows}
    security_task_rows = (
        await db.execute(
            select(
                Task.tenant_id,
                func.count(Task.id).filter(Task.type == "vuln_scan"),
                func.count(Task.id).filter(Task.type == "pentest"),
                func.count(Task.id).filter(Task.type == "ids_scan"),
            ).group_by(Task.tenant_id)
        )
    ).all()
    vuln_task_counts = {row[0]: int(row[1] or 0) for row in security_task_rows}
    pentest_task_counts = {row[0]: int(row[2] or 0) for row in security_task_rows}
    ids_task_counts = {row[0]: int(row[3] or 0) for row in security_task_rows}
    log_volume_rows = (
        await db.execute(
            select(
                LogEntry.tenant_id,
                func.sum(func.length(LogEntry.message) + func.coalesce(func.length(LogEntry.raw), 0)),
            ).group_by(LogEntry.tenant_id)
        )
    ).all()
    log_volume_gb = {
        row[0]: round(float((row[1] or 0) / (1024 ** 3)), 4)
        for row in log_volume_rows
    }

    platform_settings = next(
        (
            tenant.settings
            for tenant in tenants
            if isinstance(tenant.settings, dict) and tenant.settings.get("internal_platform")
        ),
        {},
    )
    if not isinstance(platform_settings, dict):
        platform_settings = {}
    billing_config = merge_billing_config(platform_settings.get("license_billing"))

    tenant_items = []
    for tenant in tenants:
        internal = bool((tenant.settings or {}).get("internal_platform"))
        tenant_settings = tenant.settings if isinstance(tenant.settings, dict) else {}
        consumption = {
            "hosts": int(host_counts.get(tenant.id, 0)),
            "hosts_full": int(host_full_counts.get(tenant.id, 0)),
            "hosts_infra": max(0, int(host_counts.get(tenant.id, 0)) - int(host_full_counts.get(tenant.id, 0))),
            "network_assets": int(asset_counts.get(tenant.id, 0)),
            "users": int(user_counts.get(tenant.id, 0)),
            "synthetics": int(synthetic_counts.get(tenant.id, 0)),
            "extension_units": int(extension_metric_units.get(tenant.id, 0)),
            "snmp_assets": int(snmp_asset_counts.get(tenant.id, 0)),
            "discovered_assets": int(discovered_asset_counts.get(tenant.id, 0)),
            "logs_gb": float(log_volume_gb.get(tenant.id, 0.0)),
            "trace_count": int(trace_counts.get(tenant.id, 0)),
            "rum_events": int(rum_counts.get(tenant.id, 0)),
            "ids_alerts": int(ids_counts.get(tenant.id, 0)),
            "security_events": int(security_event_counts.get(tenant.id, 0)),
            "vulnerability_scans": int(vuln_task_counts.get(tenant.id, 0)),
            "pentest_runs": int(pentest_task_counts.get(tenant.id, 0)),
            "ids_tasks": int(ids_task_counts.get(tenant.id, 0)),
        }
        consumption["weighted_units"] = (
            consumption["hosts"] * 2
            + consumption["network_assets"]
            + consumption["synthetics"]
            + consumption["extension_units"]
        )
        consumption["billing_units"] = {
            "hosts_infra_hours": consumption["hosts_infra"] * 24 * 30,
            "hosts_full_hours": consumption["hosts_full"] * 24 * 30,
            "logs_gb": round(consumption["logs_gb"], 3),
            "snmp_devices": consumption["snmp_assets"],
            "discovered_devices": consumption["discovered_assets"],
            "security_units": (
                consumption["ids_alerts"]
                + consumption["security_events"]
                + consumption["vulnerability_scans"]
                + consumption["pentest_runs"]
                + consumption["ids_tasks"]
            ),
            "vulnerability_host_scans": consumption["vulnerability_scans"],
            "vulnerability_app_scans": 0,
            "pentest_units": consumption["pentest_runs"],
            "observability_units": max(
                consumption["hosts_full"],
                int((consumption["trace_count"] + consumption["rum_events"]) / 1000),
            ),
            "integration_metric_units": consumption["extension_units"],
        }
        billing = simulate_billing(
            consumption["billing_units"],
            billing_config,
            plan=str(tenant.plan).replace("PlanType.", ""),
            internal=internal,
            assigned_package=str(tenant_settings.get("billing_package") or "").strip() or None,
        )
        tenant_items.append(
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "plan": str(tenant.plan).replace("PlanType.", ""),
                "internal": internal,
                "max_hosts": tenant.max_hosts,
                "max_agents": tenant.max_agents,
                "max_users": tenant.max_users,
                "consumption": consumption,
                "billing": billing,
                "assigned_billing_package": tenant_settings.get("billing_package"),
            }
        )

    customer_tenants = [tenant for tenant in tenant_items if not tenant["internal"]]
    payg_total = round(sum(float(item["billing"]["payg_total"]) for item in customer_tenants), 2)
    best_total = round(sum(float((item["billing"].get("selected_option") or item["billing"]["best_option"])["total"]) for item in customer_tenants), 2)
    return {
        "platform": {
            "name": "LAS Plataforma de Monitoramento e Observabilidade",
            "api_url": "https://api.soservices.com.br",
            "frontend_url": "https://las.soservices.com.br",
        },
        "billing_config": {
            "currency": billing_config["currency"],
            "billing_cycle": billing_config["billing_cycle"],
            "notes": billing_config["notes"],
            "units": [
                {
                    "code": code,
                    **LICENSE_BILLING_UNIT_CATALOG[code],
                    **billing_config["units"][code],
                }
                for code in LICENSE_BILLING_UNIT_CATALOG
            ],
        },
        "summary": {
            "tenant_customers": len(customer_tenants),
            "tenant_internal": len(tenant_items) - len(customer_tenants),
            "hosts": sum(item["consumption"]["hosts"] for item in customer_tenants),
            "network_assets": sum(item["consumption"]["network_assets"] for item in customer_tenants),
            "users": sum(item["consumption"]["users"] for item in customer_tenants),
            "synthetics": sum(item["consumption"]["synthetics"] for item in customer_tenants),
        },
        "billing_summary": {
            "payg_total": payg_total,
            "best_total": best_total,
            "estimated_savings": round(max(0.0, payg_total - best_total), 2),
            "customer_tenants": len(customer_tenants),
        },
        "tenants": tenant_items,
    }


@router.get("/admin/runtime")
async def admin_runtime(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)

    since = datetime.now(timezone.utc) - timedelta(hours=24)

    tenants = (await db.execute(select(Tenant).order_by(Tenant.name))).scalars().all()
    gateways = (await db.execute(select(Gateway).order_by(Gateway.tenant_id, Gateway.name))).scalars().all()

    tenant_map = {tenant.id: tenant for tenant in tenants}
    gateway_summary_by_tenant: dict[str, dict] = {}
    for gateway in gateways:
        tenant = tenant_map.get(gateway.tenant_id)
        tenant_name = tenant.name if tenant else gateway.tenant_id
        item = gateway_summary_by_tenant.setdefault(
            gateway.tenant_id,
            {
                "tenant_id": gateway.tenant_id,
                "tenant_name": tenant_name,
                "internal": bool((tenant.settings or {}).get("internal_platform")) if tenant else False,
                "online": 0,
                "stale": 0,
                "offline": 0,
                "total": 0,
            },
        )
        gateway_status, _ = gateway_health(gateway)
        item["total"] += 1
        if gateway_status == "online":
            item["online"] += 1
        elif gateway_status == "stale":
            item["stale"] += 1
        else:
            item["offline"] += 1

    metric_count = (
        await db.execute(
            select(func.count(HostMetric.id)).where(HostMetric.timestamp >= since)
        )
    ).scalar_one()
    log_count = (
        await db.execute(
            select(func.count(LogEntry.id)).where(LogEntry.timestamp >= since)
        )
    ).scalar_one()
    trace_count = (
        await db.execute(
            select(func.count(OtelTrace.id)).where(OtelTrace.start_time >= since)
        )
    ).scalar_one()

    expected_api_instances = int(os.getenv("API_CLUSTER_EXPECTED_REPLICAS", "2"))
    ha_mode = os.getenv("HA_MODE", "active-passive").strip().lower()
    instance_metrics = await list_instance_metrics()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_cluster": {
            "mode": ha_mode,
            "expected_instances": expected_api_instances,
            "active_instances": len(instance_metrics) or (expected_api_instances if ha_mode == "active-active" else 1),
            "frontend_proxy": "nginx-ha",
            "api_url": settings.PLATFORM_URL,
            "frontend_url": settings.PUBLIC_WEB_URL,
            "instances": instance_metrics,
        },
        "dependencies": {
            "postgres": {
                "host": settings.POSTGRES_HOST,
                "port": settings.POSTGRES_PORT,
                "mode": os.getenv("POSTGRES_HA_MODE", "single"),
            },
            "redis": {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "mode": os.getenv("REDIS_HA_MODE", "single"),
                "sentinels": [item.strip() for item in (settings.REDIS_SENTINELS or "").split(",") if item.strip()],
            },
        },
        "ingestion_last_24h": {
            "metrics": int(metric_count or 0),
            "logs": int(log_count or 0),
            "traces": int(trace_count or 0),
        },
        "gateway_health": {
            "online": sum(item["online"] for item in gateway_summary_by_tenant.values()),
            "stale": sum(item["stale"] for item in gateway_summary_by_tenant.values()),
            "offline": sum(item["offline"] for item in gateway_summary_by_tenant.values()),
            "tenants": list(gateway_summary_by_tenant.values()),
        },
        "cluster_design": {
            "tenant_policy": "2 gateways primarios + 1 failover por tenant",
            "shared_policy": "cluster compartilhado do tenant interno opcional para fallback",
            "agent_strategy": "priority-weighted-failover",
        },
    }


@router.post("/platform/tenants")
@router.post("/tenants")
async def create_tenant(
    payload: TenantCreatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    slug = slugify(payload.slug or payload.name)
    admin_email = (payload.admin_email or "").strip() or None
    admin_username = (payload.admin_username or username_from_email_or_name(admin_email, payload.admin_name or payload.name)).strip()
    admin_name = (payload.admin_name or admin_username or payload.name).strip()
    admin_user_email = admin_email or f"{admin_username}@tenant.local"
    tenant_exists_conditions = [Tenant.slug == slug]
    if admin_email:
        tenant_exists_conditions.append(Tenant.admin_email == admin_email)
    existing = await db.execute(select(Tenant).where(or_(*tenant_exists_conditions)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant slug or admin email already exists")

    user_exists_conditions = [User.username == admin_username]
    if admin_email:
        user_exists_conditions.append(User.email == admin_email)
    existing_user = await db.execute(select(User).where(or_(*user_exists_conditions)))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Admin username or email already exists")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        slug=slug,
        admin_name=admin_name,
        admin_email=admin_email,
        plan=normalize_plan(payload.plan),
        status="active",
        max_hosts=1000,
        max_agents=1000,
        max_users=100,
        features={
            "agents": True,
            "gateways": True,
            "otel": True,
            "logs": True,
            "alerts": True,
            "network_discovery": True,
            "snmp": True,
        },
        settings={"company_name": payload.name, "platform_name": "LAS Plataforma de Monitoramento e Observabilidade"},
    )
    db.add(tenant)
    await db.flush()

    admin_user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        username=admin_username,
        email=admin_user_email,
        full_name=admin_name,
        password_hash=hash_password(payload.admin_password),
        role="admin",
        active=True,
        must_change_password=True,
    )
    db.add(admin_user)

    # Create mirror tenant (slug-0) for platform self-monitoring per customer.
    # This is internal-only and visible to the superadmin for diagnostics/support.
    await ensure_mirror_tenant(db, tenant)
    await db.commit()
    return {"status": "created", "tenant_id": tenant.id, "admin_user_id": admin_user.id}


@router.put("/platform/tenants/{tenant_id}")
@router.patch("/platform/tenants/{tenant_id}")
@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.name = payload.name
    tenant.admin_name = payload.admin_name or tenant.admin_name
    tenant.admin_email = payload.admin_email or tenant.admin_email
    tenant.status = payload.status
    tenant.plan = normalize_plan(payload.plan)
    await db.commit()
    return {"status": "saved"}


@router.post("/platform/impersonate")
@router.post("/admin/impersonate")
async def impersonate_user(
    payload: ImpersonatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    query = select(User).where(User.active == True)
    if payload.user_id:
        query = query.where(User.id == payload.user_id)
    elif payload.email:
        query = query.where(User.email == payload.email.strip().lower())
    elif payload.username:
        query = query.where(User.username == payload.username.strip())
    elif payload.tenant_id:
        query = query.where(User.tenant_id == payload.tenant_id, User.role.in_(["admin", "operator"]))
    else:
        raise HTTPException(status_code=422, detail="Inform a user_id, email, username or tenant_id")
    target_user = (await db.execute(query.order_by(User.role, User.email).limit(1))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    tenant = await db.get(Tenant, target_user.tenant_id)
    session = Session(
        id=str(uuid.uuid4()),
        token=secrets.token_urlsafe(32),
        user_id=target_user.id,
        tenant_id=target_user.tenant_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        last_activity=datetime.now(timezone.utc),
        active=True,
    )
    db.add(session)
    await db.commit()
    return {
        "status": "ok",
        "access_token": session.token,
        "token_type": "bearer",
        "expires_in": 4 * 60 * 60,
        "impersonated_user": {
            "id": target_user.id,
            "username": target_user.username,
            "email": target_user.email,
            "name": target_user.full_name,
            "role": target_user.role,
            "tenant_id": target_user.tenant_id,
            "tenant_name": tenant.name if tenant else None,
        },
    }


@router.get("/network-assets")
async def list_network_assets(
    q: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    snmp_enabled: Optional[bool] = Query(None),
    syslog_enabled: Optional[bool] = Query(None),
    manufacturer: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(NetworkAsset)
        .where(
            NetworkAsset.tenant_id == user.tenant_id,
            NetworkAsset.asset_type.in_(NETWORK_ASSET_TYPES),
        )
        .order_by(desc(NetworkAsset.last_scan), NetworkAsset.ip)
    )
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                NetworkAsset.hostname.ilike(like),
                NetworkAsset.ip.ilike(like),
                NetworkAsset.model.ilike(like),
                NetworkAsset.manufacturer.ilike(like),
            )
        )
    if group:
        query = query.where(NetworkAsset.group == group)
    if asset_type:
        query = query.where(NetworkAsset.asset_type == asset_type)
    if snmp_enabled is not None:
        query = query.where(NetworkAsset.snmp_enabled == snmp_enabled)
    if syslog_enabled is not None:
        query = query.where(NetworkAsset.syslog_enabled == syslog_enabled)
    if manufacturer:
        query = query.where(NetworkAsset.manufacturer.ilike(f"%{manufacturer}%"))

    result = await db.execute(query.limit(500))
    assets = result.scalars().all()
    return [
        {
            "id": asset.id,
            "hostname": asset.hostname,
            "ip": asset.ip,
            "asset_type": asset.asset_type,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "os_firmware": asset.os_firmware,
            "group": asset.group,
            "snmp_enabled": asset.snmp_enabled,
            "syslog_enabled": asset.syslog_enabled,
            "status": asset.status,
            "port_count": asset.port_count,
            "ports_up": asset.ports_up,
            "ports_down": asset.ports_down,
            "features": asset.features or [],
            "last_scan": asset.last_scan.isoformat() if asset.last_scan else None,
            "last_poll": asset.last_poll.isoformat() if asset.last_poll else None,
        }
        for asset in assets
    ]


@router.post("/network-assets/discovery")
async def start_network_discovery(
    payload: DiscoveryPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    gateway = await select_task_gateway(db, user.tenant_id, payload.gateway_id)
    command = {
        "cidr": payload.cidr,
        "ports": payload.ports,
        "timeout_ms": payload.timeout_ms,
        "snmp_community": payload.snmp_community,
    }
    task = Task(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        name=f"Discovery {payload.cidr}",
        type="network_scan",
        status="pending",
        priority="high",
        target=payload.cidr,
        description="Scan/discovery de rede com identificação de portas e SNMP.",
        scheduled_at=datetime.now(timezone.utc),
        created_by=user.id,
        result={"cidr": payload.cidr, "ports": payload.ports, "command": command},
    )
    if gateway:
        task.description = f"Scan/discovery de rede executado pelo gateway {gateway.name}."
        task.result = {
            "gateway_execution": True,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
            "command": command,
        }
        db.add(task)
        await db.commit()
        return {
            "status": "queued_gateway",
            "task_id": task.id,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
        }

    db.add(task)
    await db.commit()
    launch_runtime_task(
        task.id,
        run_network_discovery(task.id, user.tenant_id, payload.cidr, payload.ports, payload.snmp_community, payload.timeout_ms),
    )
    return {"status": "scheduled", "task_id": task.id}


@router.post("/network-assets/{asset_id}/snmp-refresh")
async def refresh_snmp_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    asset = await db.get(NetworkAsset, asset_id)
    if not asset or asset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Network asset not found")
    gateway = await select_task_gateway(db, user.tenant_id)
    command = {
        "asset_id": asset.id,
        "ip": asset.ip,
        "snmp_port": asset.snmp_port or 161,
        "snmp_community": asset.snmp_community or "public",
    }
    task = Task(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        name=f"SNMP refresh {asset.ip}",
        type="snmp_discovery",
        status="pending",
        priority="medium",
        target=asset.ip,
        description="Coleta SNMP básica do ativo de rede.",
        scheduled_at=datetime.now(timezone.utc),
        created_by=user.id,
        result={"command": command},
    )
    if gateway:
        task.description = f"Coleta SNMP executada pelo gateway {gateway.name}."
        task.result = {
            "gateway_execution": True,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
            "command": command,
        }
        db.add(task)
        await db.commit()
        return {
            "status": "queued_gateway",
            "task_id": task.id,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
        }

    db.add(task)
    await db.commit()
    launch_runtime_task(task.id, run_snmp_refresh(task.id, user.tenant_id, asset_id))
    return {"status": "scheduled", "task_id": task.id}


@router.post("/network-assets/snmp-get")
async def snmp_get_network_asset(
    payload: SnmpGetPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    gateway = await select_task_gateway(db, user.tenant_id, payload.gateway_id)
    command = {
        "ip": payload.ip,
        "oid": payload.oid,
        "snmp_port": payload.snmp_port,
        "snmp_community": payload.snmp_community,
    }
    task = Task(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        name=f"SNMP GET {payload.ip}",
        type="snmp_get",
        status="pending",
        priority="medium",
        target=payload.ip,
        description=f"SNMP GET do OID {payload.oid}.",
        scheduled_at=datetime.now(timezone.utc),
        created_by=user.id,
        result={"command": command},
    )
    if gateway:
        task.description = f"SNMP GET executado pelo gateway {gateway.name}."
        task.result = {
            "gateway_execution": True,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
            "command": command,
        }
        db.add(task)
        await db.commit()
        return {
            "status": "queued_gateway",
            "task_id": task.id,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
        }

    db.add(task)
    await db.commit()
    launch_runtime_task(
        task.id,
        run_snmp_get(task.id, user.tenant_id, payload.ip, payload.snmp_community, payload.oid, payload.snmp_port),
    )
    return {"status": "scheduled", "task_id": task.id}


@router.get("/tasks")
async def list_tasks(
    task_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Task).where(Task.tenant_id == user.tenant_id).order_by(desc(Task.created_at))
    if task_type:
        query = query.where(Task.type == task_type)
    result = await db.execute(query.limit(300))
    tasks = result.scalars().all()
    return [
        {
            "id": task.id,
            "name": task.name,
            "type": task.type,
            "status": task.status,
            "priority": task.priority,
            "target": task.target,
            "description": task.description,
            "progress": task.progress,
            "error": task.error,
            "result": task.result,
            "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "recurrence": task.recurrence,
        }
        for task in tasks
    ]


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task or task.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    logs = list(task.logs or [])
    if task.error and not any(str(item.get("message") or item.get("msg") or "").strip() == task.error for item in logs if isinstance(item, dict)):
        logs.append(
            {
                "ts": (task.completed_at or task.started_at or datetime.now(timezone.utc)).isoformat(),
                "level": "error",
                "message": task.error,
            }
        )
    return {
        "id": task.id,
        "name": task.name,
        "type": task.type,
        "status": task.status,
        "priority": task.priority,
        "target": task.target,
        "description": task.description,
        "progress": task.progress,
        "error": task.error,
        "result": task.result or {},
        "logs": logs,
        "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "recurrence": task.recurrence,
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    task = await db.get(Task, task_id)
    if not task or task.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    cancelled = cancel_runtime_task(task_id)
    if not cancelled and task.status not in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Task cannot be cancelled")
    task.status = "cancelled"
    task.completed_at = datetime.now(timezone.utc)
    task.progress = 100
    await db.commit()
    return {"status": "cancelled"}


@router.get("/alerts/rules")
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AlertRule).where(AlertRule.tenant_id == user.tenant_id).order_by(AlertRule.name))
    return [
        {
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "entity_type": rule.entity_type,
            "entity_ids": rule.entity_ids or [],
            "tags_filter": rule.tags_filter or [],
            "metric": rule.metric,
            "condition_op": rule.condition_op,
            "threshold_value": rule.threshold_value,
            "duration_seconds": rule.duration_seconds,
            "severity": rule.severity,
            "enabled": rule.enabled,
            "channels": rule.channels or [],
            "use_baseline": rule.use_baseline,
            "baseline_sensitivity": rule.baseline_sensitivity,
            "suppress_seconds": rule.suppress_seconds,
        }
        for rule in result.scalars().all()
    ]


@router.post("/alerts/rules")
async def create_alert_rule(
    payload: AlertRulePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    rule = AlertRule(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        entity_type=payload.entity_type,
        metric=payload.metric,
        condition_op=payload.condition_op,
        threshold_value=payload.threshold_value,
        duration_seconds=payload.duration_seconds,
        entity_ids=payload.entity_ids,
        tags_filter=payload.tags_filter,
        severity=payload.severity,
        channels=payload.channels,
        use_baseline=payload.use_baseline,
        baseline_sensitivity=payload.baseline_sensitivity,
        suppress_seconds=payload.suppress_seconds,
        enabled=payload.enabled,
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    return {"status": "created", "rule_id": rule.id}


@router.put("/alerts/rules/{rule_id}")
@router.patch("/alerts/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    payload: AlertRulePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    rule = await db.get(AlertRule, rule_id)
    if not rule or rule.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    rule.name = payload.name
    rule.description = payload.description
    rule.entity_type = payload.entity_type
    rule.entity_ids = payload.entity_ids
    rule.tags_filter = payload.tags_filter
    rule.metric = payload.metric
    rule.condition_op = payload.condition_op
    rule.threshold_value = payload.threshold_value
    rule.duration_seconds = payload.duration_seconds
    rule.severity = payload.severity
    rule.channels = payload.channels
    rule.use_baseline = payload.use_baseline
    rule.baseline_sensitivity = payload.baseline_sensitivity
    rule.suppress_seconds = payload.suppress_seconds
    rule.enabled = payload.enabled
    await db.commit()
    return {"status": "saved", "rule_id": rule.id}


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    rule = await db.get(AlertRule, rule_id)
    if not rule or rule.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "rule_id": rule_id}


@router.get("/alerts")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Alert)
        .where(Alert.tenant_id == user.tenant_id)
        .order_by(desc(Alert.triggered_at))
        .limit(300)
    )
    return [
        {
            "id": alert.id,
            "name": alert.name,
            "description": alert.description,
            "severity": alert.severity,
            "status": alert.status,
            "entity_type": alert.entity_type,
            "entity_name": alert.entity_name,
            "metric": alert.metric,
            "observed_value": alert.observed_value,
            "threshold_value": alert.threshold_value,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        }
        for alert in result.scalars().all()
    ]


@router.get("/extensions")
async def list_extensions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ext_result = await db.execute(select(Extension).where(Extension.is_active == True).order_by(Extension.name))
    cfg_result = await db.execute(select(ExtensionConfig).where(ExtensionConfig.tenant_id == user.tenant_id))
    configs = cfg_result.scalars().all()
    configs_by_ext: dict[str, list[ExtensionConfig]] = {}
    for cfg in configs:
        configs_by_ext.setdefault(cfg.extension_id, []).append(cfg)
    extensions = ext_result.scalars().all()
    return [
        {
            "id": ext.id,
            "slug": ext.slug,
            "name": ext.name,
            "description": ext.description,
            "category": ext.category,
            "version": ext.version,
            "author": ext.author,
            "is_official": ext.is_official,
            "installed": ext.id in configs_by_ext,
            "enabled": any(cfg.enabled for cfg in configs_by_ext.get(ext.id, [])) if ext.id in configs_by_ext else False,
            "instances": len(configs_by_ext.get(ext.id, [])),
            "last_status": (sorted(
                [cfg for cfg in configs_by_ext.get(ext.id, []) if cfg.last_check],
                key=lambda cfg: cfg.last_check,
                reverse=True,
            )[0].last_status if any(cfg.last_check for cfg in configs_by_ext.get(ext.id, [])) else (
                configs_by_ext.get(ext.id, [None])[0].last_status if configs_by_ext.get(ext.id) else None
            )),
            "metrics": ext.metrics or [],
        }
        for ext in extensions
    ]


@router.get("/extensions/{extension_slug}")
async def get_extension_detail(
    extension_slug: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    ext_result = await db.execute(select(Extension).where(Extension.slug == extension_slug, Extension.is_active == True))
    extension = ext_result.scalar_one_or_none()
    if not extension:
        raise HTTPException(status_code=404, detail="Extension not found")
    cfg_result = await db.execute(
        select(ExtensionConfig).where(
            ExtensionConfig.tenant_id == user.tenant_id,
            ExtensionConfig.extension_id == extension.id,
        ).order_by(desc(ExtensionConfig.last_check), ExtensionConfig.name)
    )
    instances = cfg_result.scalars().all()
    return {
        "extension": {
            "id": extension.id,
            "slug": extension.slug,
            "name": extension.name,
            "description": extension.description,
            "category": extension.category,
            "version": extension.version,
            "author": extension.author,
            "metrics": extension.metrics or [],
            "config_schema": extension.config_schema or {},
            "readme": extension.readme,
        },
        "instances": [
            {
                "id": cfg.id,
                "name": cfg.name,
                "enabled": cfg.enabled,
                "run_on": cfg.run_on,
                "gateway_type": cfg.gateway_type,
                "interval_seconds": cfg.interval_seconds,
                "last_check": cfg.last_check.isoformat() if cfg.last_check else None,
                "last_status": cfg.last_status,
                "last_error": cfg.last_error,
                "metrics_collected": cfg.metrics_collected or 0,
                "config": cfg.config or {},
            }
            for cfg in instances
        ],
    }


async def select_extension_gateway(
    db: AsyncSession,
    tenant_id: str,
    gateway_type: Optional[str] = None,
) -> Gateway | None:
    query = select(Gateway).where(Gateway.tenant_id == tenant_id, Gateway.status == "online")
    if gateway_type:
        query = query.where(Gateway.type == gateway_type)
    query = query.order_by(desc(Gateway.last_heartbeat), Gateway.name).limit(50)
    result = await db.execute(query)
    for gateway in result.scalars().all():
        modules = ((gateway.config or {}).get("last_metadata") or {}).get("modules") or {}
        if gateway.type == "integrations" or modules.get("integrations") or modules.get("database") or modules.get("itsm") or modules.get("webhooks"):
            return gateway
    return None


@router.post("/extensions/{extension_slug}/instances")
async def create_extension_instance(
    extension_slug: str,
    payload: ExtensionInstancePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    ext_result = await db.execute(select(Extension).where(Extension.slug == extension_slug, Extension.is_active == True))
    extension = ext_result.scalar_one_or_none()
    if not extension:
        raise HTTPException(status_code=404, detail="Extension not found")
    instance = ExtensionConfig(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        extension_id=extension.id,
        name=payload.name.strip() or "default",
        enabled=payload.enabled,
        config=payload.config or {},
        run_on=(payload.run_on or "auto"),
        gateway_type=(payload.gateway_type or None),
        interval_seconds=max(60, int(payload.interval_seconds or 300)),
        last_status="configured",
    )
    db.add(instance)
    await db.commit()
    return {"status": "created", "id": instance.id}


@router.put("/extensions/instances/{instance_id}")
async def update_extension_instance(
    instance_id: str,
    payload: ExtensionInstancePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    instance = await db.get(ExtensionConfig, instance_id)
    if not instance or instance.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Extension instance not found")
    instance.name = payload.name.strip() or instance.name
    instance.enabled = payload.enabled
    instance.config = payload.config or {}
    instance.run_on = payload.run_on or instance.run_on
    instance.gateway_type = payload.gateway_type or instance.gateway_type
    instance.interval_seconds = max(60, int(payload.interval_seconds or instance.interval_seconds or 300))
    instance.last_status = "configured"
    await db.commit()
    return {"status": "saved"}


@router.delete("/extensions/instances/{instance_id}")
async def delete_extension_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    instance = await db.get(ExtensionConfig, instance_id)
    if not instance or instance.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Extension instance not found")
    await db.delete(instance)
    await db.commit()
    return {"status": "deleted"}


@router.post("/extensions/instances/{instance_id}/run")
async def run_extension_instance_now(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    instance = await db.get(ExtensionConfig, instance_id)
    if not instance or instance.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Extension instance not found")
    extension = await db.get(Extension, instance.extension_id)
    if not extension or not extension.is_active:
        raise HTTPException(status_code=404, detail="Extension not found")

    run_on = (instance.run_on or "auto").lower()

    gateway = await select_extension_gateway(db, user.tenant_id, instance.gateway_type or "integrations")
    if not gateway:
        raise HTTPException(status_code=503, detail="No online gateway available to execute this extension")

    command = {
        "extension_slug": extension.slug,
        "instance_id": instance.id,
        "instance_name": instance.name,
        "config": instance.config or {},
        "preferred_executor": run_on,
    }
    task = Task(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        name=f"Extension {extension.slug} ({instance.name})",
        type="extension_collect",
        status="pending",
        priority="medium",
        target=instance.id,
        description=f"Execucao de extensao via gateway {gateway.name} com executor preferencial {run_on}.",
        scheduled_at=datetime.now(timezone.utc),
        created_by=user.id,
        result={
            "gateway_execution": True,
            "gateway_id": gateway.id,
            "gateway_name": gateway.name,
            "command": command,
        },
    )
    db.add(task)
    await db.commit()
    return {"status": "queued_gateway", "task_id": task.id, "gateway_id": gateway.id}


@router.post("/extensions/config")
async def save_extension_config(
    payload: ExtensionConfigPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    ext_result = await db.execute(select(Extension).where(Extension.slug == payload.extension_slug))
    extension = ext_result.scalar_one_or_none()
    if not extension:
        raise HTTPException(status_code=404, detail="Extension not found")
    cfg_result = await db.execute(
        select(ExtensionConfig).where(
            ExtensionConfig.tenant_id == user.tenant_id,
            ExtensionConfig.extension_id == extension.id,
            ExtensionConfig.name == "default",
        )
    )
    config = cfg_result.scalar_one_or_none()
    if not config:
        config = ExtensionConfig(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            extension_id=extension.id,
            name="default",
        )
        db.add(config)
    config.enabled = payload.enabled
    config.config = payload.config
    config.last_status = "configured"
    await db.commit()
    return {"status": "saved"}


@router.get("/hosts/{host_id}/settings")
async def get_host_settings(
    host_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    host = await db.get(Host, host_id)
    if not host or host.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Host not found")
    return {
        "id": host.id,
        "hostname": host.hostname,
        "ip": host.ip,
        "monitoring_mode": host.monitoring_mode,
        "otel_enabled": host.otel_enabled,
        "log_collection": host.log_collection,
        "ids_enabled": host.ids_enabled,
        "vuln_scan_enabled": host.vuln_scan_enabled,
        "apm_enabled": host.apm_enabled,
        "tags": host.tags or [],
        "log_paths": host.log_paths or [],
        "detected_log_paths": (host.custom_config or {}).get("detected_log_paths") or [],
        "detected_log_paths_at": (host.custom_config or {}).get("detected_log_paths_at"),
        "technology_inventory": (host.custom_config or {}).get("technology_inventory") or [],
        "technology_inventory_at": (host.custom_config or {}).get("technology_inventory_at"),
    }


@router.put("/hosts/{host_id}/settings")
async def update_host_settings(
    host_id: str,
    payload: HostConfigPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    host = await db.get(Host, host_id)
    if not host or host.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Host not found")

    tenant = await db.get(Tenant, user.tenant_id)
    licenses = tenant_license_codes(tenant) if tenant else {"infra", "included"}
    required: set[str] = set()
    want_full = payload.monitoring_mode in {"infra+otel"} or payload.otel_enabled or payload.apm_enabled
    if want_full:
        required.add("complete")
    if payload.ids_enabled:
        required.add("sec")
    if payload.vuln_scan_enabled:
        required.add("vulnerability_hosts")
    missing = sorted([code for code in required if code not in licenses])
    if missing:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Funcionalidade nao licenciada para este tenant",
                "missing_licenses": missing,
                "licenses": sorted(licenses),
            },
        )

    # Optional hard limits (SaaS and on-prem): can live in tenant.settings.limits or be provisioned by edge sync.
    limits = (tenant.settings or {}).get("limits") if tenant and isinstance(tenant.settings, dict) else {}
    if not isinstance(limits, dict):
        limits = {}
    max_hosts_full = int(limits.get("max_hosts_full") or 0)
    if want_full and max_hosts_full > 0:
        current_full = bool(host.otel_enabled or host.apm_enabled or host.monitoring_mode == "infra+otel")
        if not current_full:
            full_count = (
                await db.execute(
                    select(func.count(Host.id)).where(
                        Host.tenant_id == user.tenant_id,
                        or_(
                            Host.otel_enabled == True,
                            Host.apm_enabled == True,
                            Host.monitoring_mode == "infra+otel",
                        ),
                    )
                )
            ).scalar_one_or_none() or 0
            if int(full_count) + 1 > max_hosts_full:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "message": "Limite de hosts completos (OTel/APM) excedido para este tenant",
                        "limit": max_hosts_full,
                        "current": int(full_count),
                    },
                )

    host.monitoring_mode = payload.monitoring_mode
    host.otel_enabled = payload.otel_enabled
    host.log_collection = payload.log_collection
    host.ids_enabled = payload.ids_enabled
    host.vuln_scan_enabled = payload.vuln_scan_enabled
    host.apm_enabled = payload.apm_enabled
    host.tags = payload.tags
    host.log_paths = payload.log_paths
    await db.commit()
    return {"status": "saved"}
