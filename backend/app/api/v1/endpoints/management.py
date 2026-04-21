"""Management endpoints for tenants, discovery, SNMP, tasks, alerts and integrations."""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import (
    AlertRule,
    Extension,
    ExtensionConfig,
    Gateway,
    Host,
    HostMetric,
    LogEntry,
    NetworkAsset,
    OtelTrace,
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
from app.services.license_service import tenant_license_codes

router = APIRouter(tags=["management"])
NETWORK_ASSET_TYPES = {"network", "switch", "router", "firewall", "ap", "hub", "access_point", "wifi", "wireless", "printer", "ups"}


def require_admin(user: User) -> None:
    if user.role not in {"superadmin", "admin"}:
        raise HTTPException(status_code=403, detail="Administrator role required")


def require_superadmin(user: User) -> None:
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin role required")


class TenantCreatePayload(BaseModel):
    name: str
    slug: str
    admin_name: str
    admin_email: Optional[str] = None
    admin_username: str
    admin_password: str = Field(min_length=4)
    plan: str = "enterprise"


class TenantUpdatePayload(BaseModel):
    name: str
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    status: str = "active"
    plan: str = "enterprise"


class DiscoveryPayload(BaseModel):
    cidr: str
    ports: list[int] = Field(default_factory=lambda: [22, 80, 443, 161, 3389, 514, 8080, 8443])
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
    query = query.order_by(desc(Gateway.last_heartbeat), Gateway.name).limit(20)
    result = await db.execute(query)
    for gateway in result.scalars().all():
        modules = ((gateway.config or {}).get("last_metadata") or {}).get("modules") or {}
        if modules.get("network_discovery") or modules.get("snmp"):
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


class ExtensionConfigPayload(BaseModel):
    extension_slug: str
    enabled: bool = True
    config: dict = Field(default_factory=dict)


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


@router.get("/admin/overview")
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

    tenant_items = []
    for tenant in tenants:
        internal = bool((tenant.settings or {}).get("internal_platform"))
        consumption = {
            "hosts": int(host_counts.get(tenant.id, 0)),
            "hosts_full": int(host_full_counts.get(tenant.id, 0)),
            "hosts_infra": max(0, int(host_counts.get(tenant.id, 0)) - int(host_full_counts.get(tenant.id, 0))),
            "network_assets": int(asset_counts.get(tenant.id, 0)),
            "users": int(user_counts.get(tenant.id, 0)),
            "synthetics": int(synthetic_counts.get(tenant.id, 0)),
        }
        consumption["weighted_units"] = (
            consumption["hosts"] * 2
            + consumption["network_assets"]
            + consumption["synthetics"]
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
            }
        )

    customer_tenants = [tenant for tenant in tenant_items if not tenant["internal"]]
    return {
        "platform": {
            "name": "LAS Plataforma de Monitoramento e Observabilidade",
            "api_url": "https://api.soservices.com.br",
            "frontend_url": "https://las.soservices.com.br",
        },
        "summary": {
            "tenant_customers": len(customer_tenants),
            "tenant_internal": len(tenant_items) - len(customer_tenants),
            "hosts": sum(item["consumption"]["hosts"] for item in customer_tenants),
            "network_assets": sum(item["consumption"]["network_assets"] for item in customer_tenants),
            "users": sum(item["consumption"]["users"] for item in customer_tenants),
            "synthetics": sum(item["consumption"]["synthetics"] for item in customer_tenants),
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


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_superadmin(user)
    slug = re.sub(r"[^a-z0-9-]", "-", payload.slug.lower()).strip("-")
    admin_email = (payload.admin_email or "").strip() or None
    admin_user_email = admin_email or f"{payload.admin_username}@tenant.local"
    tenant_exists_conditions = [Tenant.slug == slug]
    if admin_email:
        tenant_exists_conditions.append(Tenant.admin_email == admin_email)
    existing = await db.execute(select(Tenant).where(or_(*tenant_exists_conditions)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant slug or admin email already exists")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        slug=slug,
        admin_name=payload.admin_name,
        admin_email=admin_email,
        plan=payload.plan,
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
        username=payload.admin_username,
        email=admin_user_email,
        full_name=payload.admin_name,
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
    tenant.plan = payload.plan
    await db.commit()
    return {"status": "saved"}


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
            "metric": rule.metric,
            "condition_op": rule.condition_op,
            "threshold_value": rule.threshold_value,
            "duration_seconds": rule.duration_seconds,
            "severity": rule.severity,
            "enabled": rule.enabled,
            "channels": rule.channels or [],
            "use_baseline": rule.use_baseline,
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
        severity=payload.severity,
        channels=payload.channels,
        use_baseline=payload.use_baseline,
        enabled=True,
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    return {"status": "created", "rule_id": rule.id}


@router.get("/extensions")
async def list_extensions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ext_result = await db.execute(select(Extension).where(Extension.is_active == True).order_by(Extension.name))
    cfg_result = await db.execute(select(ExtensionConfig).where(ExtensionConfig.tenant_id == user.tenant_id))
    configs = {cfg.extension_id: cfg for cfg in cfg_result.scalars().all()}
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
            "installed": ext.id in configs,
            "enabled": configs.get(ext.id).enabled if ext.id in configs else False,
            "metrics": ext.metrics or [],
        }
        for ext in extensions
    ]


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
        )
    )
    config = cfg_result.scalar_one_or_none()
    if not config:
        config = ExtensionConfig(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            extension_id=extension.id,
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
