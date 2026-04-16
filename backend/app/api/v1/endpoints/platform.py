"""Operational API endpoints for the LAS web frontend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import Integer, and_, desc, exists, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import (
    AgentToken,
    Alert,
    AlertRule,
    Dashboard,
    DashboardWidget,
    Gateway,
    Host,
    HostMetric,
    LogEntry,
    NetworkAsset,
    NetworkPort,
    NotificationChannel,
    Extension,
    ExtensionConfig,
    IdsAlert,
    OtelTrace,
    OtelSpan,
    OtelMetric,
    RumEvent,
    RumSession,
    SecurityEvent,
    SyntheticResult,
    SyntheticTest,
    Task,
    Tenant,
    User,
)
from app.services.gateway_routing import gateway_health, gateway_public_url, resolve_gateway_routes
from app.services.token_service import create_gateway_token

router = APIRouter(tags=["platform"])
NETWORK_ASSET_TYPES = {"network", "switch", "router", "firewall", "ap", "hub", "access_point", "wifi", "wireless", "printer", "ups"}

TIMEFRAME_DELTAS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "today": None,
    "24h": timedelta(hours=24),
    "72h": timedelta(hours=72),
    "1w": timedelta(days=7),
    "30d": timedelta(days=30),
}


def parse_timeframe(
    timeframe: str = "1h",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if timeframe == "custom":
        range_end = end or now
        range_start = start or (range_end - timedelta(hours=1))
        if range_start.tzinfo is None:
            range_start = range_start.replace(tzinfo=timezone.utc)
        if range_end.tzinfo is None:
            range_end = range_end.replace(tzinfo=timezone.utc)
        if range_end < range_start:
            raise HTTPException(status_code=400, detail="Invalid custom timeframe")
        if range_end - range_start > timedelta(days=365):
            raise HTTPException(status_code=400, detail="Custom timeframe cannot exceed 365 days")
        return range_start, range_end
    if timeframe == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    delta = TIMEFRAME_DELTAS.get(timeframe)
    if not delta:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    return now - delta, now


def clean_setting_value(value: Optional[str], max_length: int | None = None) -> Optional[str]:
    """Normalize values that may come from .env files with inline comments."""
    if value is None:
        return None
    cleaned = value.split("#", 1)[0].strip()
    if not cleaned:
        return None
    if max_length is not None:
        return cleaned[:max_length]
    return cleaned


class SettingsPayload(BaseModel):
    company_name: str
    platform_name: str
    platform_url: str
    public_web_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_from: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    theme_primary: Optional[str] = None
    theme_secondary: Optional[str] = None
    theme_surface: Optional[str] = None


class NotificationChannelPayload(BaseModel):
    name: str
    type: str
    enabled: bool = True
    config: dict = {}


class GatewayCreatePayload(BaseModel):
    name: str
    type: str = "infra"
    host: Optional[str] = None
    port: int = 9443
    priority: int = 100
    weight: int = 1
    cluster_name: str = "default"
    failover_only: bool = False
    shared_with_tenants: bool = False
    public_endpoint: Optional[str] = None
    tls_enabled: bool = True
    compress_enabled: bool = True
    encrypt_enabled: bool = True


class GatewayUpdatePayload(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    cluster_name: Optional[str] = None
    failover_only: Optional[bool] = None
    shared_with_tenants: Optional[bool] = None
    public_endpoint: Optional[str] = None
    tls_enabled: Optional[bool] = None
    compress_enabled: Optional[bool] = None
    encrypt_enabled: Optional[bool] = None


class GatewayCleanupPayload(BaseModel):
    delete_names: list[str] = []
    delete_prefixes: list[str] = []
    delete_offline_only: bool = False


class SyntheticPayload(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "url_monitor"
    enabled: bool = True
    url: Optional[str] = None
    method: str = "GET"
    headers: dict = {}
    body: Optional[str] = None
    auth_type: Optional[str] = None
    auth_value: Optional[str] = None
    interval_seconds: int = 60
    timeout_seconds: int = 30
    assertions: list[dict] = []
    ssl_warn_days: int = 30
    ssl_crit_days: int = 7
    flow_steps: list[dict] = []
    playwright_script: Optional[str] = None
    alert_on_failure: bool = True
    consecutive_failures_threshold: int = 2


class LogProcessingConfigPayload(BaseModel):
    levels: list[str] = ["info", "warn", "error", "critical"]


class LogMonitorPayload(BaseModel):
    name: str
    query: Optional[str] = None
    host: Optional[str] = None
    ip: Optional[str] = None
    source: Optional[str] = None
    level: Optional[str] = None
    service: Optional[str] = None
    group: Optional[str] = None
    timeframe: str = "24h"
    viz_type: str = "timeseries"
    threshold_count: Optional[float] = None
    severity: str = "medium"
    create_alert: bool = False


class DashboardPayload(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "custom"
    time_range: str = "1h"
    is_public: bool = True


class DashboardWidgetPayload(BaseModel):
    title: str
    viz_type: str = "timeseries"
    metric: Optional[str] = None
    query: Optional[str] = None
    entity_type: Optional[str] = None
    group_by: Optional[str] = None
    aggregation: str = "avg"
    options: dict = {}


def serialize_gateway(gateway: Gateway) -> dict:
    effective_status, healthy = gateway_health(gateway)
    return {
        "id": gateway.id,
        "name": gateway.name,
        "type": gateway.type,
        "host": gateway.host,
        "port": gateway.port,
        "status": effective_status,
        "stored_status": gateway.status,
        "healthy": healthy,
        "version": gateway.version,
        "priority": int((gateway.config or {}).get("priority", 100)),
        "weight": int((gateway.config or {}).get("weight", 1)),
        "cluster_name": (gateway.config or {}).get("cluster_name", "default"),
        "failover_only": bool((gateway.config or {}).get("failover_only", False)),
        "shared_with_tenants": bool((gateway.config or {}).get("shared_with_tenants", False)),
        "public_endpoint": (gateway.config or {}).get("public_endpoint") or gateway_public_url(gateway),
        "tls_enabled": gateway.tls_enabled,
        "compress_enabled": gateway.compress_enabled,
        "encrypt_enabled": gateway.encrypt_enabled,
        "last_heartbeat": gateway.last_heartbeat.isoformat() if gateway.last_heartbeat else None,
    }


def host_is_not_network_asset_condition():
    return ~exists(
        select(NetworkAsset.id).where(
            NetworkAsset.tenant_id == Host.tenant_id,
            NetworkAsset.ip == Host.ip,
            NetworkAsset.asset_type.in_(NETWORK_ASSET_TYPES),
        )
    )


def host_is_not_merged_condition():
    return Host.custom_config["merged_into"].as_string().is_(None)


def host_display_key(host: Host) -> str:
    name = (host.hostname or "").strip().lower()
    if name and not name.startswith("192.") and name != (host.ip or "").strip().lower():
        return f"name:{name}"
    aliases = sorted(host_aliases(host))
    return f"ip:{aliases[0]}" if aliases else f"id:{host.id}"


def infer_application_name(url: str | None, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if not url:
        return "Aplicacao sem URL"
    path = "/" + url.split("://", 1)[-1].split("/", 1)[-1].split("?", 1)[0]
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "Raiz"
    root = parts[0]
    if root.lower() == "las":
        if len(parts) == 1 or parts[1].lower() in {"home", "index", "portal"}:
            return "LAS Home"
        return f"LAS {parts[1].replace('-', ' ').replace('_', ' ').title()}"
    return root.replace("-", " ").replace("_", " ").title()


def topology_node(
    node_id: str,
    label: str,
    node_type: str,
    status: str | None = None,
    subtitle: str | None = None,
    metrics: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "status": status or "unknown",
        "subtitle": subtitle,
        "metrics": metrics or {},
        "metadata": metadata or {},
    }


def topology_edge(
    source: str,
    target: str,
    label: str,
    edge_type: str,
    metrics: dict | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": f"{source}->{target}:{edge_type}:{label}",
        "source": source,
        "target": target,
        "label": label,
        "type": edge_type,
        "status": status or "ok",
        "metrics": metrics or {},
        "metadata": metadata or {},
    }


def compact_url_host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except ValueError:
        return None


def normalize_process_name(name: str | None) -> str:
    return str(name or "").strip().lower().split("/")[-1].split("\\")[-1]


def host_aliases(host: Host) -> set[str]:
    values = {host.hostname, host.ip}
    cfg = host.custom_config or {}
    for ip in cfg.get("known_ips") or []:
        values.add(ip)
    for interface in cfg.get("interfaces") or []:
        for address in interface.get("addresses") or []:
            values.add(address)
    return {str(value).lower() for value in values if value}


def increment_edge(edge_map: dict[str, dict], edge: dict, count_field: str = "requests") -> None:
    existing = edge_map.setdefault(edge["id"], edge)
    existing["metrics"][count_field] = int(existing["metrics"].get(count_field) or 0) + int(edge["metrics"].get(count_field) or 1)
    if edge["metrics"].get("errors"):
        existing["metrics"]["errors"] = int(existing["metrics"].get("errors") or 0) + int(edge["metrics"].get("errors") or 0)


def default_dashboard_blueprints() -> list[dict]:
    return [
        {
            "id": "system-hosts",
            "name": "Hosts - Infraestrutura",
            "category": "host",
            "description": "CPU, memoria, disco, rede, processos e incidentes por host.",
            "is_system": True,
            "widgets": [
                {"title": "CPU por host", "viz_type": "timeseries", "metric": "host.cpu_usage", "aggregation": "avg", "entity_type": "host"},
                {"title": "Memoria usada", "viz_type": "area", "metric": "host.memory_usage", "aggregation": "avg", "entity_type": "host"},
                {"title": "Rede In/Out", "viz_type": "timeseries", "metric": "host.network_bytes", "aggregation": "sum", "entity_type": "host"},
                {"title": "Top processos", "viz_type": "table", "metric": "host.processes", "aggregation": "max", "entity_type": "host"},
            ],
        },
        {
            "id": "system-services",
            "name": "Servicos e OpenTelemetry",
            "category": "service",
            "description": "Latencia, erros, requests, traces e dependencias de servicos.",
            "is_system": True,
            "widgets": [
                {"title": "Requests por servico", "viz_type": "timeseries", "metric": "otel.requests", "aggregation": "sum", "entity_type": "service"},
                {"title": "Erros por servico", "viz_type": "bar", "metric": "otel.errors", "aggregation": "sum", "entity_type": "service"},
                {"title": "Latencia p95", "viz_type": "area", "metric": "otel.duration_ms", "aggregation": "p95", "entity_type": "service"},
            ],
        },
        {
            "id": "system-applications",
            "name": "Aplicacoes e RUM",
            "category": "app",
            "description": "Sessoes, satisfacao, erros JS, actions e requests por aplicacao.",
            "is_system": True,
            "widgets": [
                {"title": "Satisfacao do usuario", "viz_type": "gauge", "metric": "rum.satisfaction_index", "aggregation": "avg", "entity_type": "application"},
                {"title": "Sessoes live", "viz_type": "stat", "metric": "rum.sessions.live", "aggregation": "sum", "entity_type": "application"},
                {"title": "Erros Javascript", "viz_type": "timeseries", "metric": "rum.javascript_errors", "aggregation": "sum", "entity_type": "application"},
            ],
        },
        {
            "id": "system-network",
            "name": "Ativos de Rede",
            "category": "network",
            "description": "Portas, utilizacao, erros, drops, SNMP e syslog por ativo.",
            "is_system": True,
            "widgets": [
                {"title": "Utilizacao de portas", "viz_type": "heatmap", "metric": "network.port.utilization_pct", "aggregation": "avg", "entity_type": "network_asset"},
                {"title": "Erros e drops", "viz_type": "bar", "metric": "network.port.errors_drops", "aggregation": "sum", "entity_type": "network_asset"},
            ],
        },
        {
            "id": "system-databases",
            "name": "Bancos de Dados",
            "category": "database",
            "description": "Vendors, conexoes, queries/statements, erros e pool.",
            "is_system": True,
            "widgets": [
                {"title": "Bancos por vendor", "viz_type": "donut", "metric": "database.vendor.count", "aggregation": "count", "entity_type": "database"},
                {"title": "Queries e statements", "viz_type": "table", "metric": "database.statements", "aggregation": "sum", "entity_type": "database"},
                {"title": "Erros de query/conexao", "viz_type": "timeseries", "metric": "database.errors", "aggregation": "sum", "entity_type": "database"},
            ],
        },
        {
            "id": "system-messaging",
            "name": "Filas e Mensageria",
            "category": "messaging",
            "description": "Queues, topicos, namespaces, lag, consumidores e mensagens com erro.",
            "is_system": True,
            "widgets": [
                {"title": "Lag por fila/topico", "viz_type": "timeseries", "metric": "messaging.consumer_lag", "aggregation": "max", "entity_type": "messaging"},
                {"title": "Mensagens publicadas/consumidas", "viz_type": "area", "metric": "messaging.messages", "aggregation": "sum", "entity_type": "messaging"},
                {"title": "Dead letter / erros", "viz_type": "bar", "metric": "messaging.errors", "aggregation": "sum", "entity_type": "messaging"},
            ],
        },
        {
            "id": "system-security",
            "name": "Seguranca e Incidentes",
            "category": "security",
            "description": "IDS, vulnerabilidades, incidentes, severidade e tempo de resolucao.",
            "is_system": True,
            "widgets": [
                {"title": "Incidentes por severidade", "viz_type": "honeycomb", "metric": "alerts.by_severity", "aggregation": "count", "entity_type": "incident"},
                {"title": "IDS por origem", "viz_type": "table", "metric": "ids.source_ip", "aggregation": "count", "entity_type": "security"},
            ],
        },
    ]


@router.get("/dashboard/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant_id = user.tenant_id

    async def count(model, *conditions):
        result = await db.execute(select(func.count()).select_from(model).where(*conditions))
        return result.scalar_one()

    host_count = await count(Host, Host.tenant_id == tenant_id, host_is_not_network_asset_condition(), host_is_not_merged_condition())
    online_hosts = await count(Host, Host.tenant_id == tenant_id, Host.status == "online", host_is_not_network_asset_condition(), host_is_not_merged_condition())
    alert_count = await count(Alert, Alert.tenant_id == tenant_id, Alert.status == "active")
    trace_count = await count(OtelTrace, OtelTrace.tenant_id == tenant_id)
    log_count = await count(LogEntry, LogEntry.tenant_id == tenant_id)
    gateway_count = await count(Gateway, Gateway.tenant_id == tenant_id)
    token_count = await count(AgentToken, AgentToken.tenant_id == tenant_id, AgentToken.active == True)

    latest_hosts = await db.execute(
        select(Host)
        .where(Host.tenant_id == tenant_id, host_is_not_network_asset_condition(), host_is_not_merged_condition())
        .order_by(desc(Host.last_seen), desc(Host.created_at))
        .limit(5)
    )
    latest_logs = await db.execute(
        select(LogEntry)
        .where(LogEntry.tenant_id == tenant_id)
        .order_by(desc(LogEntry.timestamp), desc(LogEntry.created_at))
        .limit(10)
    )
    latest_traces = await db.execute(
        select(OtelTrace)
        .where(OtelTrace.tenant_id == tenant_id)
        .order_by(desc(OtelTrace.start_time), desc(OtelTrace.created_at))
        .limit(10)
    )
    problem_hosts_result = await db.execute(
        select(Host)
        .where(
            Host.tenant_id == tenant_id,
            host_is_not_network_asset_condition(),
            host_is_not_merged_condition(),
            Host.status.notin_(["online", "ok", "active"]),
        )
        .order_by(desc(Host.last_seen), Host.hostname)
        .limit(10)
    )
    latest_incidents_result = await db.execute(
        select(Alert)
        .where(Alert.tenant_id == tenant_id)
        .order_by(desc(Alert.triggered_at), desc(Alert.created_at))
        .limit(10)
    )

    cpu_avg_result = await db.execute(
        select(func.avg(Host.cpu_usage)).where(Host.tenant_id == tenant_id, host_is_not_network_asset_condition(), host_is_not_merged_condition())
    )
    mem_avg_result = await db.execute(
        select(func.avg(Host.memory_usage)).where(Host.tenant_id == tenant_id, host_is_not_network_asset_condition(), host_is_not_merged_condition())
    )

    return {
        "app_name": settings.APP_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counters": {
            "hosts_total": host_count,
            "hosts_online": online_hosts,
            "alerts_active": alert_count,
            "traces_total": trace_count,
            "logs_total": log_count,
            "gateways_total": gateway_count,
            "agent_tokens_active": token_count,
            "hosts_problem": max(host_count - online_hosts, 0),
        },
        "utilization": {
            "cpu_avg": round(float(cpu_avg_result.scalar() or 0), 2),
            "memory_avg": round(float(mem_avg_result.scalar() or 0), 2),
        },
        "hosts": [
            {
                "id": host.id,
                "hostname": host.hostname,
                "ip": host.ip,
                "status": host.status,
                "cpu_usage": host.cpu_usage,
                "memory_usage": host.memory_usage,
                "disk_usage": host.disk_usage,
                "last_seen": host.last_seen.isoformat() if host.last_seen else None,
            }
            for host in latest_hosts.scalars().all()
        ],
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "source": log.source,
                "host_name": log.host_name,
                "message": log.message,
            }
            for log in latest_logs.scalars().all()
        ],
        "traces": [
            {
                "id": trace.id,
                "trace_id": trace.trace_id,
                "service": trace.service,
                "name": trace.name,
                "status": trace.status,
                "duration_ms": trace.duration_ms,
                "start_time": trace.start_time.isoformat() if trace.start_time else None,
            }
            for trace in latest_traces.scalars().all()
        ],
        "problem_hosts": [
            {
                "id": host.id,
                "hostname": host.hostname,
                "ip": host.ip,
                "status": host.status,
                "cpu_usage": host.cpu_usage,
                "memory_usage": host.memory_usage,
                "disk_usage": host.disk_usage,
                "last_seen": host.last_seen.isoformat() if host.last_seen else None,
            }
            for host in problem_hosts_result.scalars().all()
        ],
        "incidents": [
            {
                "id": alert.id,
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity,
                "status": alert.status,
                "entity_type": alert.entity_type,
                "entity_id": alert.entity_id,
                "entity_name": alert.entity_name,
                "metric": alert.metric,
                "observed_value": alert.observed_value,
                "threshold_value": alert.threshold_value,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            }
            for alert in latest_incidents_result.scalars().all()
        ],
    }


@router.get("/hosts")
async def list_hosts(
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Host).where(
        Host.tenant_id == user.tenant_id,
        host_is_not_network_asset_condition(),
        host_is_not_merged_condition(),
    ).order_by(desc(Host.last_seen), Host.hostname)
    if q:
        like = f"%{q}%"
        query = query.where(
            Host.hostname.ilike(like) | Host.ip.ilike(like) | Host.os.ilike(like)
        )
    if status_filter:
        query = query.where(Host.status == status_filter)

    result = await db.execute(query.limit(300))
    deduped: dict[str, Host] = {}
    for host in result.scalars().all():
        key = host_display_key(host)
        current = deduped.get(key)
        if not current:
            deduped[key] = host
            continue
        current_rank = (1 if current.agent_version else 0, current.last_seen or datetime.min.replace(tzinfo=timezone.utc))
        next_rank = (1 if host.agent_version else 0, host.last_seen or datetime.min.replace(tzinfo=timezone.utc))
        if next_rank > current_rank:
            deduped[key] = host
    hosts = sorted(deduped.values(), key=lambda item: (item.last_seen or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[:100]
    return [
        {
            "id": host.id,
            "hostname": host.hostname,
            "ip": host.ip,
            "interfaces": (host.custom_config or {}).get("interfaces") or [],
            "known_ips": (host.custom_config or {}).get("known_ips") or ([host.ip] if host.ip else []),
            "os": host.os,
            "os_version": host.os_version,
            "status": host.status,
            "agent_version": host.agent_version,
            "monitoring_mode": host.monitoring_mode,
            "agent_installed": bool(host.agent_version),
            "otel_enabled": host.otel_enabled,
            "log_collection": host.log_collection,
            "ids_enabled": host.ids_enabled,
            "vuln_scan_enabled": host.vuln_scan_enabled,
            "tags": host.tags or [],
            "cpu_usage": host.cpu_usage,
            "memory_usage": host.memory_usage,
            "disk_usage": host.disk_usage,
            "uptime": host.uptime,
            "last_seen": host.last_seen.isoformat() if host.last_seen else None,
        }
        for host in hosts
    ]


@router.get("/hosts/{host_id}/detail")
async def get_host_detail(
    host_id: str,
    timeframe: str = Query("1h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    host = await db.get(Host, host_id)
    if not host or host.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Host not found")

    metrics_result = await db.execute(
        select(HostMetric)
        .where(
            HostMetric.tenant_id == user.tenant_id,
            HostMetric.host_id == host.id,
            HostMetric.timestamp >= range_start,
            HostMetric.timestamp <= range_end,
        )
        .order_by(HostMetric.timestamp)
        .limit(500)
    )
    logs_result = await db.execute(
        select(LogEntry)
        .where(
            LogEntry.tenant_id == user.tenant_id,
            or_(
                LogEntry.host_id == host.id,
                LogEntry.host_name == host.hostname,
                LogEntry.host_ip == host.ip,
            ),
        )
        .order_by(desc(LogEntry.timestamp), desc(LogEntry.created_at))
        .limit(5)
    )
    incidents_result = await db.execute(
        select(Alert)
        .where(
            Alert.tenant_id == user.tenant_id,
            Alert.entity_type == "host",
            Alert.entity_id == host.id,
        )
        .order_by(desc(Alert.triggered_at), desc(Alert.created_at))
        .limit(2)
    )

    custom_config = host.custom_config or {}
    return {
        "host": {
            "id": host.id,
            "hostname": host.hostname,
            "ip": host.ip,
            "interfaces": custom_config.get("interfaces") or [],
            "known_ips": custom_config.get("known_ips") or ([host.ip] if host.ip else []),
            "os": host.os,
            "os_version": host.os_version,
            "kernel": host.kernel,
            "arch": host.arch,
            "manufacturer": host.manufacturer,
            "model": host.model,
            "status": host.status,
            "agent_version": host.agent_version,
            "monitoring_mode": host.monitoring_mode,
            "otel_enabled": host.otel_enabled,
            "log_collection": host.log_collection,
            "ids_enabled": host.ids_enabled,
            "vuln_scan_enabled": host.vuln_scan_enabled,
            "apm_enabled": host.apm_enabled,
            "log_paths": host.log_paths or [],
            "detected_log_paths": custom_config.get("detected_log_paths") or [],
            "detected_log_paths_at": custom_config.get("detected_log_paths_at"),
            "cpu_cores": host.cpu_cores,
            "memory_total_mb": host.memory_total_mb,
            "disk_total_gb": host.disk_total_gb,
            "uptime": host.uptime,
            "last_seen": host.last_seen.isoformat() if host.last_seen else None,
            "tags": host.tags or [],
        },
        "timeframe": {
            "key": timeframe,
            "start": range_start.isoformat(),
            "end": range_end.isoformat(),
        },
        "metrics": [
            {
                "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
                "cpuUsage": metric.cpu_usage,
                "memoryUsage": metric.memory_usage,
                "diskUsage": metric.disk_usage,
                "netRxBytes": metric.net_rx_bytes,
                "netTxBytes": metric.net_tx_bytes,
                "diskReadBytes": metric.disk_read_bytes,
                "diskWriteBytes": metric.disk_write_bytes,
                "processesTotal": metric.processes_total,
                "processesRunning": metric.processes_running,
                "loadAvg1": metric.load_avg_1,
                "loadAvg5": metric.load_avg_5,
                "loadAvg15": metric.load_avg_15,
            }
            for metric in metrics_result.scalars().all()
        ],
        "processes": custom_config.get("latest_processes") or [],
        "processes_collected_at": custom_config.get("latest_processes_at"),
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "source": log.source,
                "host_name": log.host_name,
                "host_ip": log.host_ip,
                "service": log.service,
                "trace_id": log.trace_id,
                "message": log.message,
            }
            for log in logs_result.scalars().all()
        ],
        "incidents": [
            {
                "id": alert.id,
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity,
                "status": alert.status,
                "metric": alert.metric,
                "observed_value": alert.observed_value,
                "threshold_value": alert.threshold_value,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            }
            for alert in incidents_result.scalars().all()
        ],
    }


@router.get("/process-groups")
async def list_process_groups(
    q: Optional[str] = Query(None),
    host_filter: Optional[str] = Query(None, alias="host"),
    sort: str = Query("instances"),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    result = await db.execute(
        select(Host)
        .where(Host.tenant_id == user.tenant_id, Host.custom_config["merged_into"].as_string().is_(None))
        .order_by(Host.hostname)
    )
    groups: dict[str, dict] = {}
    for host_row in result.scalars().all():
        for proc in (host_row.custom_config or {}).get("latest_processes") or []:
            name = str(proc.get("name") or "").strip()
            if not name:
                continue
            if q and q.lower() not in name.lower():
                continue
            host_filter_value = (host_filter or "").lower()
            if host_filter_value and host_filter_value not in (host_row.hostname or "").lower() and host_filter_value not in (host_row.ip or "").lower():
                continue
            normalized = name.lower().split("/")[-1].split("\\")[-1]
            group = groups.setdefault(
                normalized,
                {
                    "name": normalized,
                    "instances": 0,
                    "hosts": set(),
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "technologies": set(),
                    "services": set(),
                },
            )
            group["instances"] += 1
            group["hosts"].add(host_row.hostname)
            group["cpu_usage"] += float(proc.get("cpuUsage") or proc.get("cpu_usage") or 0)
            group["memory_usage"] += float(proc.get("memoryUsage") or proc.get("memory_usage") or 0)
            tech = "java" if "java" in normalized or "tomcat" in normalized else "nodejs" if "node" in normalized else "python" if "python" in normalized else "dotnet" if "dotnet" in normalized else "unknown"
            group["technologies"].add(tech)
    trace_result = await db.execute(
        select(OtelTrace)
        .where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.start_time >= range_start, OtelTrace.start_time <= range_end)
        .order_by(desc(OtelTrace.start_time))
        .limit(1000)
    )
    for trace in trace_result.scalars().all():
        text = f"{trace.service or ''} {trace.name or ''} {trace.url or ''}".lower()
        for name, group in groups.items():
            if name and name in text:
                group["services"].add(trace.service)
    items = [
        {
            **{key: value for key, value in item.items() if key not in {"hosts", "technologies", "services"}},
            "hosts": sorted(item["hosts"]),
            "technologies": sorted(item["technologies"]),
            "services_count": len(item["services"]),
            "cpu_usage": round(item["cpu_usage"], 2),
            "memory_usage": round(item["memory_usage"], 2),
        }
        for item in groups.values()
    ]
    sort_key = "memory_usage" if sort in {"memory", "memoria", "ram"} else "cpu_usage" if sort == "cpu" else "instances"
    return sorted(items, key=lambda item: item.get(sort_key) or 0, reverse=True)[:100]


@router.get("/services")
async def list_services(
    q: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(OtelTrace).where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.start_time >= range_start, OtelTrace.start_time <= range_end)
    if service:
        query = query.where(OtelTrace.service.ilike(f"%{service}%"))
    if host:
        query = query.where(OtelTrace.host_name.ilike(f"%{host}%"))
    if q:
        like = f"%{q}%"
        query = query.where(or_(OtelTrace.service.ilike(like), OtelTrace.name.ilike(like), OtelTrace.url.ilike(like)))
    traces = (await db.execute(query.order_by(desc(OtelTrace.start_time)).limit(1000))).scalars().all()
    service_map: dict[str, dict] = {}
    for trace in traces:
        item = service_map.setdefault(
            trace.service,
            {
                "name": trace.service,
                "technology": (trace.resource or {}).get("telemetry.sdk.language") or "otel",
                "monitoring_mode": "otel",
                "requests": 0,
                "errors": 0,
                "duration_total": 0.0,
                "hosts": set(),
                "logs_enabled": False,
                "ids_enabled": False,
                "vuln_scan_enabled": False,
                "urls": set(),
            },
        )
        item["requests"] += 1
        item["errors"] += 1 if trace.status == "error" or (trace.response_code or 0) >= 500 else 0
        item["duration_total"] += float(trace.duration_ms or 0)
        if trace.host_name:
            item["hosts"].add(trace.host_name)
        if trace.url:
            item["urls"].add(trace.url)
    return [
        {
            **{key: value for key, value in item.items() if key not in {"hosts", "urls"}},
            "hosts": sorted(item["hosts"]),
            "avg_duration_ms": round(item["duration_total"] / max(item["requests"], 1), 2),
            "urls": sorted(item["urls"])[:10],
        }
        for item in sorted(service_map.values(), key=lambda service: service["requests"], reverse=True)[:100]
    ]


@router.get("/applications")
async def list_applications(
    q: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(OtelTrace).where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.start_time >= range_start, OtelTrace.start_time <= range_end)
    if service:
        query = query.where(OtelTrace.service.ilike(f"%{service}%"))
    if q:
        query = query.where(OtelTrace.url.ilike(f"%{q}%"))
    traces = (await db.execute(query.order_by(desc(OtelTrace.start_time)).limit(1000))).scalars().all()
    rum_query = select(RumEvent).where(RumEvent.tenant_id == user.tenant_id, RumEvent.timestamp >= range_start, RumEvent.timestamp <= range_end)
    if service:
        rum_query = rum_query.where(RumEvent.service.ilike(f"%{service}%"))
    if q:
        rum_query = rum_query.where(or_(RumEvent.application.ilike(f"%{q}%"), RumEvent.url.ilike(f"%{q}%")))
    rum_events = (await db.execute(rum_query.order_by(desc(RumEvent.timestamp)).limit(1000))).scalars().all()
    apps: dict[str, dict] = {}
    for trace in traces:
        if not trace.url:
            continue
        app_key = infer_application_name(trace.url)
        item = apps.setdefault(
            app_key,
            {
                "name": app_key,
                "requests": 0,
                "actions": 0,
                "request_errors": 0,
                "action_errors": 0,
                "javascript_errors": 0,
                "duration_total": 0.0,
                "services": set(),
                "sessions": 0,
                "users_online": 0,
                "source": "otel",
            },
        )
        item["requests"] += 1
        item["actions"] += 1 if trace.kind in {"server", "client"} else 0
        item["request_errors"] += 1 if trace.status == "error" or (trace.response_code or 0) >= 400 else 0
        item["duration_total"] += float(trace.duration_ms or 0)
        item["services"].add(trace.service)
    for event in rum_events:
        app_key = event.application or "/"
        item = apps.setdefault(
            app_key,
            {
                "name": app_key,
                "requests": 0,
                "actions": 0,
                "request_errors": 0,
                "action_errors": 0,
                "javascript_errors": 0,
                "duration_total": 0.0,
                "services": set(),
                "sessions": 0,
                "users_online": 0,
                "source": "rum",
            },
        )
        if event.event_type in {"request", "resource"}:
            item["requests"] += 1
            item["request_errors"] += 1 if (event.status_code or 0) >= 400 else 0
        elif event.event_type in {"error", "javascript_error"}:
            item["javascript_errors"] += 1
        else:
            item["actions"] += 1
            item["action_errors"] += 1 if not event.satisfied else 0
        item["duration_total"] += float(event.duration_ms or 0)
        if event.service:
            item["services"].add(event.service)
    sessions_result = await db.execute(
        select(RumSession.application, func.count(RumSession.id), func.sum(func.cast(RumSession.live, Integer)))
        .where(RumSession.tenant_id == user.tenant_id, RumSession.last_seen >= range_start, RumSession.last_seen <= range_end)
        .group_by(RumSession.application)
    )
    for app_name, session_count, live_count in sessions_result.all():
        if app_name in apps:
            apps[app_name]["sessions"] = int(session_count or 0)
            apps[app_name]["users_online"] = int(live_count or 0)
    return [
        {
            **{key: value for key, value in item.items() if key != "services"},
            "services": sorted(item["services"]),
            "satisfaction_index": max(0, round(100 - (item["request_errors"] / max(item["requests"], 1)) * 100, 2)),
            "avg_response_ms": round(item["duration_total"] / max(item["requests"], 1), 2),
        }
        for item in sorted(apps.values(), key=lambda app: app["requests"], reverse=True)[:100]
    ]


@router.get("/databases")
async def list_databases(
    q: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    configs_result = await db.execute(
        select(ExtensionConfig, Extension)
        .join(Extension, Extension.id == ExtensionConfig.extension_id)
        .where(ExtensionConfig.tenant_id == user.tenant_id, Extension.category == "database")
    )
    configs = configs_result.all()
    metric_result = await db.execute(
        select(OtelMetric)
        .where(
            OtelMetric.tenant_id == user.tenant_id,
            OtelMetric.timestamp >= range_start,
            OtelMetric.timestamp <= range_end,
            OtelMetric.metric_name.ilike("postgresql.%") | OtelMetric.metric_name.ilike("mysql.%") | OtelMetric.metric_name.ilike("sqlserver.%") | OtelMetric.metric_name.ilike("oracle.%") | OtelMetric.metric_name.ilike("mongodb.%") | OtelMetric.metric_name.ilike("redis.%"),
        )
        .order_by(desc(OtelMetric.timestamp))
        .limit(1000)
    )
    latest_by_key: dict[str, OtelMetric] = {}
    for metric in metric_result.scalars().all():
        cfg_id = (metric.labels or {}).get("extension_config_id", "unbound")
        key = f"{cfg_id}:{metric.metric_name}"
        latest_by_key.setdefault(key, metric)

    items = []
    for config, extension in configs:
        cfg = config.config or {}
        if q and q.lower() not in f"{extension.name} {extension.slug} {cfg.get('host','')} {cfg.get('database','')}".lower():
            continue
        metrics = {
            metric.metric_name: {
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
            }
            for key, metric in latest_by_key.items()
            if key.startswith(f"{config.id}:")
        }
        items.append(
            {
                "id": config.id,
                "name": extension.name,
                "engine": extension.slug,
                "host": cfg.get("host"),
                "port": cfg.get("port"),
                "database": cfg.get("database"),
                "status": config.last_status,
                "last_check": config.last_check.isoformat() if config.last_check else None,
                "metrics_collected": config.metrics_collected or 0,
                "metrics": metrics,
            }
        )
    return items


@router.get("/synthetics")
async def list_synthetics(
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(SyntheticTest).where(SyntheticTest.tenant_id == user.tenant_id).order_by(desc(SyntheticTest.last_check), SyntheticTest.name)
    if q:
        like = f"%{q}%"
        query = query.where(or_(SyntheticTest.name.ilike(like), SyntheticTest.url.ilike(like), SyntheticTest.description.ilike(like)))
    if status_filter:
        query = query.where(SyntheticTest.last_status == status_filter)
    tests = (await db.execute(query.limit(300))).scalars().all()
    latest_results = {}
    if tests:
        result_rows = await db.execute(
            select(SyntheticResult)
            .where(SyntheticResult.tenant_id == user.tenant_id, SyntheticResult.test_id.in_([test.id for test in tests]))
            .order_by(desc(SyntheticResult.timestamp))
            .limit(1000)
        )
        for result in result_rows.scalars().all():
            latest_results.setdefault(result.test_id, result)
    return [
        {
            "id": test.id,
            "name": test.name,
            "type": getattr(test.type, "value", str(test.type)),
            "enabled": test.enabled,
            "url": test.url,
            "method": test.method,
            "interval_seconds": test.interval_seconds,
            "last_status": test.last_status,
            "last_check": test.last_check.isoformat() if test.last_check else None,
            "last_response_ms": test.last_response_ms,
            "uptime_pct": test.uptime_pct,
            "latest_error": latest_results.get(test.id).error_message if latest_results.get(test.id) else None,
            "latest_ssl_days_remaining": latest_results.get(test.id).ssl_days_remaining if latest_results.get(test.id) else None,
        }
        for test in tests
    ]


@router.post("/synthetics")
async def create_synthetic(
    payload: SyntheticPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    valid_types = {"url_monitor", "api_monitor", "app_flow", "ssl_check", "dns_check", "tcp_check", "icmp_ping"}
    if payload.type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid synthetic type")
    if payload.type in {"url_monitor", "api_monitor", "app_flow", "ssl_check"} and not payload.url:
        raise HTTPException(status_code=400, detail="URL is required for this synthetic type")
    test = SyntheticTest(
        id=str(uuid4()),
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        type=payload.type,
        enabled=payload.enabled,
        url=payload.url,
        method=(payload.method or "GET").upper(),
        headers=payload.headers or {},
        body=payload.body,
        auth_type=payload.auth_type or "none",
        auth_value=payload.auth_value,
        interval_seconds=max(30, int(payload.interval_seconds or 60)),
        timeout_seconds=max(5, int(payload.timeout_seconds or 30)),
        assertions=payload.assertions or [],
        ssl_warn_days=payload.ssl_warn_days or 30,
        ssl_crit_days=payload.ssl_crit_days or 7,
        flow_steps=payload.flow_steps or [],
        playwright_script=payload.playwright_script,
        alert_on_failure=payload.alert_on_failure,
        consecutive_failures_threshold=max(1, int(payload.consecutive_failures_threshold or 2)),
        last_status="unknown",
    )
    db.add(test)
    await db.commit()
    return {"id": test.id, "status": "created"}


@router.get("/synthetics/{test_id}/detail")
async def get_synthetic_detail(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = await db.get(SyntheticTest, test_id)
    if not test or test.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Synthetic test not found")
    results = (
        await db.execute(
            select(SyntheticResult)
            .where(SyntheticResult.tenant_id == user.tenant_id, SyntheticResult.test_id == test.id)
            .order_by(desc(SyntheticResult.timestamp))
            .limit(100)
        )
    ).scalars().all()
    return {
        "test": {
            "id": test.id,
            "name": test.name,
            "description": test.description,
            "type": getattr(test.type, "value", str(test.type)),
            "enabled": test.enabled,
            "url": test.url,
            "method": test.method,
            "headers": test.headers or {},
            "auth_type": test.auth_type,
            "interval_seconds": test.interval_seconds,
            "timeout_seconds": test.timeout_seconds,
            "assertions": test.assertions or [],
            "ssl_warn_days": test.ssl_warn_days,
            "ssl_crit_days": test.ssl_crit_days,
            "flow_steps": test.flow_steps or [],
            "last_status": test.last_status,
            "last_check": test.last_check.isoformat() if test.last_check else None,
            "last_response_ms": test.last_response_ms,
            "uptime_pct": test.uptime_pct,
            "avg_response_ms": test.avg_response_ms,
        },
        "results": [
            {
                "id": result.id,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                "location": result.location,
                "status": result.status,
                "response_time_ms": result.response_time_ms,
                "status_code": result.status_code,
                "ssl_valid": result.ssl_valid,
                "ssl_expires_at": result.ssl_expires_at.isoformat() if result.ssl_expires_at else None,
                "ssl_days_remaining": result.ssl_days_remaining,
                "ssl_issuer": result.ssl_issuer,
                "assertions_passed": result.assertions_passed,
                "assertions_failed": result.assertions_failed,
                "assertion_details": result.assertion_details or [],
                "steps_total": result.steps_total,
                "steps_passed": result.steps_passed,
                "step_details": result.step_details or [],
                "error_message": result.error_message,
                "response_body_snippet": result.response_body_snippet,
            }
            for result in results
        ],
    }


@router.post("/synthetics/{test_id}/run")
async def run_synthetic_now(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = await db.get(SyntheticTest, test_id)
    if not test or test.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Synthetic test not found")
    try:
        from app.workers.synthetic_worker import run_api_monitor, run_app_flow, run_ssl_check, run_url_monitor

        test_type = getattr(test.type, "value", str(test.type))
        if test_type == "ssl_check":
            task = run_ssl_check.apply_async(args=[test.id])
        elif test_type == "app_flow":
            task = run_app_flow.apply_async(args=[test.id])
        elif test_type == "api_monitor":
            task = run_api_monitor.apply_async(args=[test.id])
        else:
            task = run_url_monitor.apply_async(args=[test.id])
        return {"status": "queued", "task_id": task.id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to queue synthetic test: {exc}") from exc


@router.get("/incidents")
async def list_incidents(
    limit: int = Query(100, ge=1, le=500),
    q: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    timeframe: str = Query("30d"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(Alert).where(Alert.tenant_id == user.tenant_id, Alert.triggered_at >= range_start, Alert.triggered_at <= range_end)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Alert.name.ilike(like), Alert.description.ilike(like), Alert.entity_name.ilike(like), Alert.metric.ilike(like)))
    if host:
        query = query.where(Alert.entity_name.ilike(f"%{host}%"))
    if status_filter:
        query = query.where(Alert.status == status_filter)
    if severity:
        query = query.where(Alert.severity == severity)
    result = await db.execute(
        query
        .order_by(desc(Alert.triggered_at), desc(Alert.created_at))
        .limit(limit)
    )
    return [
        {
            "id": alert.id,
            "name": alert.name,
            "description": alert.description,
            "severity": alert.severity,
            "status": alert.status,
            "entity_type": alert.entity_type,
            "entity_id": alert.entity_id,
            "entity_name": alert.entity_name,
            "metric": alert.metric,
            "observed_value": alert.observed_value,
            "threshold_value": alert.threshold_value,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        }
        for alert in result.scalars().all()
    ]


@router.get("/security/vulnerabilities")
async def list_security_vulnerabilities(
    timeframe: str = Query("30d"),
    host: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe)
    query = select(Alert).where(
        Alert.tenant_id == user.tenant_id,
        Alert.triggered_at >= range_start,
        Alert.triggered_at <= range_end,
        or_(Alert.metric.ilike("%vuln%"), Alert.name.ilike("%vulner%"), Alert.description.ilike("%CVE%")),
    )
    if host:
        query = query.where(Alert.entity_name.ilike(f"%{host}%"))
    if severity:
        query = query.where(Alert.severity == severity)
    rows = (await db.execute(query.order_by(desc(Alert.triggered_at)).limit(300))).scalars().all()
    return [
        {
            "id": item.id,
            "title": item.name,
            "description": item.description,
            "severity": item.severity,
            "status": item.status,
            "host": item.entity_name,
            "entity_type": item.entity_type,
            "metric": item.metric,
            "triggered_at": item.triggered_at.isoformat() if item.triggered_at else None,
        }
        for item in rows
    ]


@router.get("/security/ids")
async def list_security_ids(
    timeframe: str = Query("30d"),
    host: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe)
    query = (
        select(IdsAlert, Host)
        .outerjoin(Host, Host.id == IdsAlert.host_id)
        .where(IdsAlert.tenant_id == user.tenant_id, IdsAlert.timestamp >= range_start, IdsAlert.timestamp <= range_end)
    )
    if host:
        like = f"%{host}%"
        query = query.where(or_(Host.hostname.ilike(like), IdsAlert.dest_ip.ilike(like), IdsAlert.source_ip.ilike(like)))
    if severity:
        query = query.where(IdsAlert.severity == severity)
    rows = (await db.execute(query.order_by(desc(IdsAlert.timestamp)).limit(500))).all()
    return [
        {
            "id": alert.id,
            "host": host_row.hostname if host_row else alert.dest_ip,
            "severity": alert.severity,
            "category": alert.category,
            "attack_type": alert.attack_type,
            "source_ip": alert.source_ip,
            "dest_ip": alert.dest_ip,
            "dest_port": alert.dest_port,
            "attempts": alert.attempts,
            "status": alert.status,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
            "ai_summary": alert.ai_summary,
        }
        for alert, host_row in rows
    ]


@router.get("/security/pentest")
async def list_security_pentest(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tasks = (
        await db.execute(
            select(Task)
            .where(Task.tenant_id == user.tenant_id, Task.type.in_(["pentest", "pentest_scan"]))
            .order_by(desc(Task.created_at))
            .limit(200)
        )
    ).scalars().all()
    return [
        {
            "id": task.id,
            "name": task.name,
            "status": task.status,
            "target": task.target,
            "progress": task.progress,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result,
            "error": task.error,
        }
        for task in tasks
    ]


@router.get("/topologies/{scope}")
async def get_topology(
    scope: str,
    q: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    application: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scope = scope.lower()
    valid_scopes = {"network", "processes", "services", "applications", "hosts"}
    if scope not in valid_scopes:
        raise HTTPException(status_code=400, detail="Invalid topology scope")
    range_start, range_end = parse_timeframe(timeframe, start, end)
    notes: list[str] = []
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}

    hosts = (
        await db.execute(
            select(Host)
            .where(Host.tenant_id == user.tenant_id, Host.custom_config["merged_into"].as_string().is_(None), host_is_not_network_asset_condition())
            .order_by(Host.hostname)
            .limit(1000)
        )
    ).scalars().all()
    assets = (
        await db.execute(
            select(NetworkAsset)
            .where(NetworkAsset.tenant_id == user.tenant_id, NetworkAsset.asset_type.in_(NETWORK_ASSET_TYPES))
            .order_by(NetworkAsset.hostname, NetworkAsset.ip)
            .limit(1000)
        )
    ).scalars().all()
    ports = (
        await db.execute(
            select(NetworkPort)
            .where(NetworkPort.tenant_id == user.tenant_id)
            .order_by(NetworkPort.asset_id, NetworkPort.port_number)
            .limit(4000)
        )
    ).scalars().all()
    trace_query = select(OtelTrace).where(
        OtelTrace.tenant_id == user.tenant_id,
        OtelTrace.start_time >= range_start,
        OtelTrace.start_time <= range_end,
    )
    if host:
        trace_query = trace_query.where(OtelTrace.host_name.ilike(f"%{host}%"))
    if service:
        trace_query = trace_query.where(OtelTrace.service.ilike(f"%{service}%"))
    traces = (await db.execute(trace_query.order_by(desc(OtelTrace.start_time)).limit(2500))).scalars().all()

    host_by_alias: dict[str, Host] = {}
    for item in hosts:
        for alias in host_aliases(item):
            host_by_alias[alias] = item
    asset_by_id = {asset.id: asset for asset in assets}
    asset_by_alias = {
        str(value).lower(): asset
        for asset in assets
        for value in {asset.hostname, asset.ip, asset.mac}
        if value
    }

    def add_host_node(item: Host) -> str:
        node_id = f"host:{item.id}"
        nodes[node_id] = topology_node(
            node_id,
            item.hostname,
            "host",
            item.status,
            item.ip,
            {
                "cpu_pct": round(float(item.cpu_usage or 0), 2),
                "memory_pct": round(float(item.memory_usage or 0), 2),
                "disk_pct": round(float(item.disk_usage or 0), 2),
            },
            {"host_id": item.id, "os": item.os, "known_ips": (item.custom_config or {}).get("known_ips") or [item.ip]},
        )
        return node_id

    def add_asset_node(item: NetworkAsset) -> str:
        node_id = f"asset:{item.id}"
        nodes[node_id] = topology_node(
            node_id,
            item.hostname or item.ip,
            "network_asset",
            item.status,
            item.asset_type,
            {
                "ports": item.port_count or 0,
                "ports_up": item.ports_up or 0,
                "ports_down": item.ports_down or 0,
            },
            {"asset_id": item.id, "ip": item.ip, "manufacturer": item.manufacturer, "model": item.model},
        )
        return node_id

    if scope == "network":
        for item in hosts:
            add_host_node(item)
        for item in assets:
            add_asset_node(item)
        matched_ports = 0
        for port in ports:
            asset = asset_by_id.get(port.asset_id)
            if not asset or not port.connected_device:
                continue
            connected = str(port.connected_device).strip().lower()
            target_host = host_by_alias.get(connected)
            target_asset = asset_by_alias.get(connected)
            if not target_host and not target_asset:
                continue
            source_id = add_asset_node(asset)
            target_id = add_host_node(target_host) if target_host else add_asset_node(target_asset)
            matched_ports += 1
            edge = topology_edge(
                source_id,
                target_id,
                port.name or port.description or f"porta {port.port_number}",
                "switch_port",
                {
                    "speed_mbps": port.speed_mbps or 0,
                    "utilization_pct": round(float(port.utilization or 0), 2),
                    "rx_bytes": port.rx_bytes or 0,
                    "tx_bytes": port.tx_bytes or 0,
                    "rx_errors": port.rx_errors or 0,
                    "tx_errors": port.tx_errors or 0,
                    "rx_drops": port.rx_drops or 0,
                    "tx_drops": port.tx_drops or 0,
                },
                "warning" if (port.rx_errors or 0) + (port.tx_errors or 0) + (port.rx_drops or 0) + (port.tx_drops or 0) else (port.status or "ok"),
                {"port_number": port.port_number, "vlan": port.vlan, "media_type": port.media_type},
            )
            edges[edge["id"]] = edge
        if not matched_ports:
            notes.append("Ainda nao ha relacionamento real por LLDP/CDP/connected_device nas portas SNMP. A topologia de rede mostra os nos descobertos e sera conectada quando os switches enviarem vizinhanca/port mapping.")

    if scope in {"processes", "applications", "hosts"}:
        for item in hosts:
            if host and host.lower() not in f"{item.hostname} {item.ip}".lower():
                continue
            add_host_node(item)
            if scope == "processes":
                for proc in (item.custom_config or {}).get("latest_processes") or []:
                    name = normalize_process_name(proc.get("name"))
                    if not name or (q and q.lower() not in name.lower()):
                        continue
                    proc_id = f"process:{name}"
                    nodes[proc_id] = topology_node(
                        proc_id,
                        name,
                        "process_group",
                        "ok",
                        f"{item.hostname}",
                        {
                            "cpu_pct": round(float(proc.get("cpuUsage") or proc.get("cpu_usage") or 0), 2),
                            "memory_pct": round(float(proc.get("memoryUsage") or proc.get("memory_usage") or 0), 2),
                        },
                    )
                    edge = topology_edge(f"host:{item.id}", proc_id, "executa", "host_process", {"instances": 1})
                    increment_edge(edges, edge, "instances")

    if scope == "services":
        service_nodes: set[str] = set()
        by_trace: dict[str, list[OtelTrace]] = {}
        for trace in traces:
            if q and q.lower() not in f"{trace.service} {trace.name} {trace.url}".lower():
                continue
            service_id = f"service:{trace.service}"
            service_nodes.add(service_id)
            nodes.setdefault(service_id, topology_node(service_id, trace.service, "service", trace.status, trace.host_name, {"requests": 0, "errors": 0}))
            nodes[service_id]["metrics"]["requests"] += 1
            nodes[service_id]["metrics"]["errors"] += 1 if trace.status == "error" or (trace.response_code or 0) >= 500 else 0
            if trace.host_name:
                matched_host = next((item for item in hosts if trace.host_name.lower() in host_aliases(item)), None)
                if matched_host:
                    host_id = add_host_node(matched_host)
                    increment_edge(edges, topology_edge(host_id, service_id, "hospeda", "hosts_service", {"requests": 1}))
            if trace.is_external_call and (trace.external_service or trace.external_host):
                ext_label = trace.external_service or trace.external_host
                ext_id = f"external:{ext_label}"
                nodes.setdefault(ext_id, topology_node(ext_id, ext_label, "external_service", trace.status, trace.external_host, {"requests": 0, "errors": 0}))
                nodes[ext_id]["metrics"]["requests"] += 1
                nodes[ext_id]["metrics"]["errors"] += 1 if trace.status == "error" or (trace.response_code or 0) >= 500 else 0
                increment_edge(edges, topology_edge(service_id, ext_id, trace.name or "chamada externa", "service_dependency", {"requests": 1, "errors": 1 if trace.status == "error" else 0}))
            by_trace.setdefault(trace.trace_id, []).append(trace)
        for trace_group in by_trace.values():
            ordered = sorted(trace_group, key=lambda row: row.start_time or range_start)
            for left, right in zip(ordered, ordered[1:]):
                if left.service == right.service:
                    continue
                increment_edge(edges, topology_edge(f"service:{left.service}", f"service:{right.service}", right.name or "chamada", "service_dependency", {"requests": 1, "errors": 1 if right.status == "error" else 0}))
        if not service_nodes:
            notes.append("Nenhuma dependencia de servico encontrada no periodo selecionado. A visao depende de traces OTLP reais.")

    if scope == "processes":
        for trace in traces:
            text = f"{trace.service or ''} {trace.name or ''} {trace.url or ''}".lower()
            service_id = f"service:{trace.service}"
            nodes.setdefault(service_id, topology_node(service_id, trace.service, "service", trace.status, trace.host_name, {"requests": 0}))
            nodes[service_id]["metrics"]["requests"] += 1
            for node_id, node in list(nodes.items()):
                if node.get("type") == "process_group" and node["label"] in text:
                    increment_edge(edges, topology_edge(node_id, service_id, "publica/consome", "process_service", {"requests": 1, "errors": 1 if trace.status == "error" else 0}))
        if not any(node.get("type") == "process_group" for node in nodes.values()):
            notes.append("Nenhum snapshot real de processo foi recebido no periodo. Instale/atualize o agente no host para preencher grupos de processos.")

    if scope == "applications":
        app_filter = (application or q or "").lower()
        for trace in traces:
            app_name = infer_application_name(trace.url)
            if app_filter and app_filter not in app_name.lower() and app_filter not in (trace.url or "").lower():
                continue
            app_id = f"application:{app_name}"
            service_id = f"service:{trace.service}"
            nodes.setdefault(app_id, topology_node(app_id, app_name, "application", trace.status, compact_url_host(trace.url), {"requests": 0, "errors": 0}))
            nodes[app_id]["metrics"]["requests"] += 1
            nodes[app_id]["metrics"]["errors"] += 1 if trace.status == "error" or (trace.response_code or 0) >= 400 else 0
            nodes.setdefault(service_id, topology_node(service_id, trace.service, "service", trace.status, trace.host_name, {"requests": 0}))
            nodes[service_id]["metrics"]["requests"] += 1
            increment_edge(edges, topology_edge(app_id, service_id, trace.name or "request", "application_service", {"requests": 1, "errors": 1 if trace.status == "error" else 0}))
            if trace.host_name:
                matched_host = next((item for item in hosts if trace.host_name.lower() in host_aliases(item)), None)
                if matched_host:
                    increment_edge(edges, topology_edge(service_id, add_host_node(matched_host), "executa em", "service_host", {"requests": 1}))
            if trace.is_external_call and (trace.external_service or trace.external_host):
                ext_label = trace.external_service or trace.external_host
                ext_id = f"external:{ext_label}"
                nodes.setdefault(ext_id, topology_node(ext_id, ext_label, "external_service", trace.status, trace.external_host, {"requests": 0}))
                nodes[ext_id]["metrics"]["requests"] += 1
                increment_edge(edges, topology_edge(service_id, ext_id, "terceiro", "external_call", {"requests": 1, "errors": 1 if trace.status == "error" else 0}))
        notes.append("O caminho fisico por ativos de rede sera enriquecido quando houver LLDP/CDP/NetFlow correlacionado com as requisicoes da aplicacao.")

    if scope == "hosts":
        metrics_rows = (
            await db.execute(
                select(HostMetric)
                .where(HostMetric.tenant_id == user.tenant_id, HostMetric.timestamp >= range_start, HostMetric.timestamp <= range_end)
                .order_by(HostMetric.host_id, HostMetric.timestamp)
                .limit(10000)
            )
        ).scalars().all()
        by_host_metrics: dict[str, list[HostMetric]] = {}
        for metric in metrics_rows:
            by_host_metrics.setdefault(metric.host_id, []).append(metric)
        for item in hosts:
            node_id = add_host_node(item)
            series = by_host_metrics.get(item.id) or []
            if len(series) >= 2:
                first, last = series[0], series[-1]
                nodes[node_id]["metrics"].update({
                    "net_in_bytes": max(0, int(last.net_rx_bytes or 0) - int(first.net_rx_bytes or 0)),
                    "net_out_bytes": max(0, int(last.net_tx_bytes or 0) - int(first.net_tx_bytes or 0)),
                    "net_errors": sum(int(row.net_errors or 0) for row in series),
                })
        for trace in traces:
            source_host = next((item for item in hosts if trace.host_name and trace.host_name.lower() in host_aliases(item)), None)
            if not source_host:
                continue
            target_label = trace.external_host or compact_url_host(trace.url) or trace.external_service
            target_host = host_by_alias.get(str(target_label or "").lower())
            source_id = add_host_node(source_host)
            if target_host and target_host.id != source_host.id:
                target_id = add_host_node(target_host)
                edge_type = "host_internal"
            elif target_label:
                target_id = f"external:{target_label}"
                nodes.setdefault(target_id, topology_node(target_id, target_label, "external_service", trace.status, None, {"requests": 0}))
                edge_type = "host_external"
            else:
                continue
            increment_edge(edges, topology_edge(source_id, target_id, trace.service or trace.name or "request", edge_type, {"requests": 1, "errors": 1 if trace.status == "error" else 0, "avg_duration_ms": round(float(trace.duration_ms or 0), 2)}))
        notes.append("Latencia vem dos traces. Retransmissao, pacotes dropados e timeout por fluxo exigem coleta adicional via NetFlow/sFlow/pcap ou estatisticas de rede do agente/gateway.")

    if q and scope not in {"processes", "services", "applications"}:
        q_lower = q.lower()
        keep_nodes = {node_id for node_id, node in nodes.items() if q_lower in f"{node.get('label')} {node.get('subtitle')} {node.get('type')}".lower()}
        keep_nodes.update(edge["source"] for edge in edges.values() if edge["source"] in keep_nodes or edge["target"] in keep_nodes)
        keep_nodes.update(edge["target"] for edge in edges.values() if edge["source"] in keep_nodes or edge["target"] in keep_nodes)
        nodes = {node_id: node for node_id, node in nodes.items() if node_id in keep_nodes}
        edges = {edge_id: edge for edge_id, edge in edges.items() if edge["source"] in keep_nodes and edge["target"] in keep_nodes}

    return {
        "scope": scope,
        "timeframe": {"start": range_start.isoformat(), "end": range_end.isoformat()},
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "hosts": sum(1 for node in nodes.values() if node["type"] == "host"),
            "network_assets": sum(1 for node in nodes.values() if node["type"] == "network_asset"),
            "services": sum(1 for node in nodes.values() if node["type"] == "service"),
            "applications": sum(1 for node in nodes.values() if node["type"] == "application"),
            "external": sum(1 for node in nodes.values() if node["type"] == "external_service"),
        },
        "notes": notes,
    }


@router.get("/network-assets/{asset_id}/detail")
async def get_network_asset_detail(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset = await db.get(NetworkAsset, asset_id)
    if not asset or asset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Network asset not found")
    ports_result = await db.execute(
        select(NetworkPort)
        .where(NetworkPort.asset_id == asset.id, NetworkPort.tenant_id == user.tenant_id)
        .order_by(NetworkPort.port_number)
        .limit(512)
    )
    return {
        "asset": {
            "id": asset.id,
            "hostname": asset.hostname,
            "ip": asset.ip,
            "asset_type": asset.asset_type,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "os_firmware": asset.os_firmware,
            "serial": asset.serial,
            "status": asset.status,
            "snmp_enabled": asset.snmp_enabled,
            "syslog_enabled": asset.syslog_enabled,
            "port_count": asset.port_count,
            "ports_up": asset.ports_up,
            "ports_down": asset.ports_down,
            "ports_fiber": asset.ports_fiber,
            "ports_copper": asset.ports_copper,
            "last_scan": asset.last_scan.isoformat() if asset.last_scan else None,
            "last_poll": asset.last_poll.isoformat() if asset.last_poll else None,
            "features": asset.features or [],
        },
        "ports": [
            {
                "port_number": port.port_number,
                "name": port.name,
                "description": port.description,
                "media_type": port.media_type,
                "speed_mbps": port.speed_mbps,
                "duplex": port.duplex,
                "status": port.status,
                "vlan": port.vlan,
                "connected_device": port.connected_device,
                "utilization": port.utilization,
                "rx_bytes": port.rx_bytes,
                "tx_bytes": port.tx_bytes,
                "rx_errors": port.rx_errors,
                "tx_errors": port.tx_errors,
                "rx_drops": port.rx_drops,
                "tx_drops": port.tx_drops,
                "last_updated": port.last_updated.isoformat() if port.last_updated else None,
            }
            for port in ports_result.scalars().all()
        ],
    }


@router.get("/logs")
async def list_logs(
    limit: int = Query(20, ge=1, le=500),
    q: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(LogEntry).where(LogEntry.tenant_id == user.tenant_id, LogEntry.timestamp >= range_start, LogEntry.timestamp <= range_end)
    if q:
        like = f"%{q}%"
        query = query.where(or_(LogEntry.message.ilike(like), LogEntry.raw.ilike(like)))
    if host:
        like = f"%{host}%"
        query = query.where(or_(LogEntry.host_name.ilike(like), LogEntry.host_ip.ilike(like)))
    if ip:
        query = query.where(LogEntry.host_ip.ilike(f"%{ip}%"))
    if source:
        query = query.where(LogEntry.source.ilike(f"%{source}%"))
    if level:
        query = query.where(LogEntry.level == level)
    if group:
        query = query.where(LogEntry.group.ilike(f"%{group}%"))
    if service:
        query = query.where(LogEntry.service.ilike(f"%{service}%"))
    result = await db.execute(
        query
        .order_by(desc(LogEntry.timestamp), desc(LogEntry.created_at))
        .limit(limit)
    )
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "level": log.level,
            "source": log.source,
            "group": log.group,
            "host_name": log.host_name,
            "host_ip": log.host_ip,
            "message": log.message,
            "service": log.service,
            "trace_id": log.trace_id,
        }
        for log in result.scalars().all()
    ]


@router.get("/logs/processing-config")
async def get_log_processing_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    cfg = (tenant.settings or {}).get("log_processing") or {}
    return {
        "levels": cfg.get("levels") or ["info", "warn", "error", "critical"],
        "available_levels": ["debug", "info", "warn", "error", "critical"],
        "note": "Esta configuracao define os niveis que agentes/gateways devem processar. A aplicacao no coletor ocorre no proximo ciclo de atualizacao dos agentes/gateways.",
    }


@router.put("/logs/processing-config")
async def update_log_processing_config(
    payload: LogProcessingConfigPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    valid = {"debug", "info", "warn", "error", "critical"}
    levels = [level.lower() for level in payload.levels if level.lower() in valid]
    if not levels:
        raise HTTPException(status_code=400, detail="At least one valid log level is required")
    current = dict(tenant.settings or {})
    current["log_processing"] = {"levels": sorted(set(levels))}
    tenant.settings = current
    flag_modified(tenant, "settings")
    await db.commit()
    return {"status": "saved", "levels": current["log_processing"]["levels"]}


@router.post("/logs/monitors")
async def create_log_monitor(
    payload: LogMonitorPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dashboard_result = await db.execute(
        select(Dashboard).where(Dashboard.tenant_id == user.tenant_id, Dashboard.name == "Metricas de Logs")
    )
    dashboard = dashboard_result.scalar_one_or_none()
    if not dashboard:
        dashboard = Dashboard(
            id=str(uuid4()),
            tenant_id=user.tenant_id,
            user_id=None,
            name="Metricas de Logs",
            description="Metricas criadas a partir de pesquisas em logs.",
            category="logs",
            is_public=True,
            is_default=False,
            is_system=False,
            time_range=payload.timeframe,
        )
        db.add(dashboard)
        await db.flush()
    widget = DashboardWidget(
        id=str(uuid4()),
        tenant_id=user.tenant_id,
        dashboard_id=dashboard.id,
        title=payload.name,
        viz_type=payload.viz_type,
        datasource="nexus",
        metric=f"log_query.{payload.name.lower().replace(' ', '_')[:80]}",
        query=payload.query,
        entity_type="log",
        aggregation="count",
        group_by="level",
        options={
            "host": payload.host,
            "ip": payload.ip,
            "source": payload.source,
            "level": payload.level,
            "service": payload.service,
            "group": payload.group,
            "timeframe": payload.timeframe,
            "threshold_count": payload.threshold_count,
            "severity": payload.severity,
        },
    )
    db.add(widget)
    alert_rule = None
    if payload.create_alert and payload.threshold_count is not None:
        alert_rule = AlertRule(
            id=str(uuid4()),
            tenant_id=user.tenant_id,
            name=f"Log monitor - {payload.name}",
            description=f"Alerta criado a partir da pesquisa de logs: {payload.query or ''}",
            entity_type="log",
            entity_ids=[],
            metric=widget.metric,
            condition_op="gte",
            threshold_value=float(payload.threshold_count),
            duration_seconds=60,
            severity=payload.severity,
            created_by=user.id,
        )
        db.add(alert_rule)
    await db.commit()
    return {
        "status": "created",
        "dashboard_id": dashboard.id,
        "widget_id": widget.id,
        "alert_rule_id": alert_rule.id if alert_rule else None,
    }


@router.get("/traces")
async def list_traces(
    limit: int = Query(100, ge=1, le=500),
    q: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(OtelTrace).where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.start_time >= range_start, OtelTrace.start_time <= range_end)
    if q:
        like = f"%{q}%"
        query = query.where(or_(OtelTrace.trace_id.ilike(like), OtelTrace.name.ilike(like), OtelTrace.url.ilike(like)))
    if host:
        query = query.where(OtelTrace.host_name.ilike(f"%{host}%"))
    if service:
        query = query.where(OtelTrace.service.ilike(f"%{service}%"))
    if status_filter:
        query = query.where(OtelTrace.status == status_filter)
    result = await db.execute(
        query
        .order_by(desc(OtelTrace.start_time), desc(OtelTrace.created_at))
        .limit(limit)
    )
    return [
        {
            "id": trace.id,
            "trace_id": trace.trace_id,
            "service": trace.service,
            "name": trace.name,
            "status": trace.status,
            "duration_ms": trace.duration_ms,
            "method": trace.method,
            "url": trace.url,
            "response_code": trace.response_code,
            "start_time": trace.start_time.isoformat() if trace.start_time else None,
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "attributes": trace.attributes or {},
            "resource": trace.resource or {},
            "events": trace.events or [],
        }
        for trace in result.scalars().all()
    ]


@router.get("/dashboards")
async def list_dashboards(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    custom = (
        await db.execute(
            select(Dashboard)
            .where(Dashboard.tenant_id == user.tenant_id)
            .order_by(Dashboard.is_system.desc(), Dashboard.category, Dashboard.name)
        )
    ).scalars().all()
    widget_counts = dict(
        (
            await db.execute(
                select(DashboardWidget.dashboard_id, func.count(DashboardWidget.id))
                .where(DashboardWidget.tenant_id == user.tenant_id)
                .group_by(DashboardWidget.dashboard_id)
            )
        ).all()
    )
    custom_items = [
        {
            "id": dashboard.id,
            "name": dashboard.name,
            "description": dashboard.description,
            "category": dashboard.category,
            "is_system": dashboard.is_system,
            "is_default": dashboard.is_default,
            "time_range": dashboard.time_range,
            "auto_refresh": dashboard.auto_refresh,
            "widgets_count": int(widget_counts.get(dashboard.id, 0)),
        }
        for dashboard in custom
    ]
    return {"system": default_dashboard_blueprints(), "custom": custom_items}


@router.post("/dashboards")
async def create_dashboard(
    payload: DashboardPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dashboard = Dashboard(
        id=str(uuid4()),
        tenant_id=user.tenant_id,
        user_id=None if payload.is_public else user.id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        time_range=payload.time_range,
        is_public=payload.is_public,
        is_system=False,
        is_default=False,
    )
    db.add(dashboard)
    await db.commit()
    return {"id": dashboard.id, "status": "created"}


@router.get("/dashboards/{dashboard_id}/detail")
async def get_dashboard_detail(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if dashboard_id.startswith("system-"):
        blueprint = next((item for item in default_dashboard_blueprints() if item["id"] == dashboard_id), None)
        if not blueprint:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {
            **blueprint,
            "widgets": [
                {**widget, "id": f"{dashboard_id}:{index}", "datasource": "nexus", "options": {}}
                for index, widget in enumerate(blueprint["widgets"], start=1)
            ],
        }
    dashboard = await db.get(Dashboard, dashboard_id)
    if not dashboard or dashboard.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widgets = (
        await db.execute(
            select(DashboardWidget)
            .where(DashboardWidget.tenant_id == user.tenant_id, DashboardWidget.dashboard_id == dashboard.id)
            .order_by(DashboardWidget.grid_y, DashboardWidget.grid_x, DashboardWidget.title)
        )
    ).scalars().all()
    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": dashboard.description,
        "category": dashboard.category,
        "is_system": dashboard.is_system,
        "time_range": dashboard.time_range,
        "widgets": [
            {
                "id": widget.id,
                "title": widget.title,
                "description": widget.description,
                "viz_type": widget.viz_type,
                "metric": widget.metric,
                "query": widget.query,
                "entity_type": widget.entity_type,
                "group_by": widget.group_by,
                "aggregation": widget.aggregation,
                "options": widget.options or {},
            }
            for widget in widgets
        ],
    }


@router.post("/dashboards/{dashboard_id}/widgets")
async def create_dashboard_widget(
    dashboard_id: str,
    payload: DashboardWidgetPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dashboard = await db.get(Dashboard, dashboard_id)
    if not dashboard or dashboard.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widget = DashboardWidget(
        id=str(uuid4()),
        tenant_id=user.tenant_id,
        dashboard_id=dashboard.id,
        title=payload.title,
        viz_type=payload.viz_type,
        datasource="nexus",
        metric=payload.metric,
        query=payload.query,
        entity_type=payload.entity_type,
        group_by=payload.group_by,
        aggregation=payload.aggregation,
        options=payload.options or {},
    )
    db.add(widget)
    await db.commit()
    return {"id": widget.id, "status": "created"}


@router.get("/messaging")
async def list_messaging(
    q: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    query = select(OtelMetric).where(
        OtelMetric.tenant_id == user.tenant_id,
        OtelMetric.timestamp >= range_start,
        OtelMetric.timestamp <= range_end,
        or_(
            OtelMetric.metric_name.ilike("messaging.%"),
            OtelMetric.metric_name.ilike("queue.%"),
            OtelMetric.metric_name.ilike("kafka.%"),
            OtelMetric.metric_name.ilike("rabbitmq.%"),
            OtelMetric.metric_name.ilike("sqs.%"),
            OtelMetric.metric_name.ilike("servicebus.%"),
        ),
    )
    if q:
        query = query.where(or_(OtelMetric.metric_name.ilike(f"%{q}%"), OtelMetric.service.ilike(f"%{q}%")))
    rows = (await db.execute(query.order_by(desc(OtelMetric.timestamp)).limit(1000))).scalars().all()
    groups: dict[str, dict] = {}
    for metric in rows:
        labels = metric.labels or {}
        name = labels.get("queue") or labels.get("topic") or labels.get("messaging.destination.name") or labels.get("destination") or metric.service or "mensageria"
        item = groups.setdefault(
            name,
            {
                "name": name,
                "vendor": labels.get("messaging.system") or labels.get("vendor") or metric.metric_name.split(".", 1)[0],
                "namespace": labels.get("namespace") or labels.get("messaging.destination.template"),
                "service": metric.service,
                "metrics": {},
                "last_seen": None,
            },
        )
        current = item["metrics"].get(metric.metric_name)
        if not current or metric.timestamp > current["timestamp_raw"]:
            item["metrics"][metric.metric_name] = {
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
                "timestamp_raw": metric.timestamp,
            }
            item["last_seen"] = metric.timestamp.isoformat() if metric.timestamp else item["last_seen"]
    return [
        {
            **{key: value for key, value in item.items() if key != "metrics"},
            "metrics": {key: {sub_key: sub_value for sub_key, sub_value in value.items() if sub_key != "timestamp_raw"} for key, value in item["metrics"].items()},
        }
        for item in groups.values()
    ]


@router.get("/orchestration")
async def list_orchestration(
    q: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    metric_query = select(OtelMetric).where(
        OtelMetric.tenant_id == user.tenant_id,
        OtelMetric.timestamp >= range_start,
        OtelMetric.timestamp <= range_end,
        or_(
            OtelMetric.metric_name.ilike("k8s.%"),
            OtelMetric.metric_name.ilike("container.%"),
            OtelMetric.metric_name.ilike("docker.%"),
            OtelMetric.metric_name.ilike("openshift.%"),
            OtelMetric.metric_name.ilike("gke.%"),
            OtelMetric.metric_name.ilike("aks.%"),
        ),
    )
    if q:
        metric_query = metric_query.where(or_(OtelMetric.metric_name.ilike(f"%{q}%"), OtelMetric.service.ilike(f"%{q}%")))
    metric_rows = (await db.execute(metric_query.order_by(desc(OtelMetric.timestamp)).limit(2000))).scalars().all()

    groups: dict[str, dict] = {}
    for metric in metric_rows:
        labels = metric.labels or {}
        detected_platform = labels.get("k8s.cluster.name") and "kubernetes" or labels.get("container.runtime") or metric.metric_name.split(".", 1)[0]
        if platform and platform.lower() not in str(detected_platform).lower():
            continue
        name = (
            labels.get("k8s.pod.name")
            or labels.get("k8s.deployment.name")
            or labels.get("container.name")
            or labels.get("container.id")
            or metric.service
            or detected_platform
            or "orquestracao"
        )
        item = groups.setdefault(
            name,
            {
                "name": name,
                "platform": detected_platform,
                "cluster": labels.get("k8s.cluster.name") or labels.get("cluster"),
                "namespace": labels.get("k8s.namespace.name") or labels.get("namespace"),
                "node": labels.get("k8s.node.name") or labels.get("host.name"),
                "workload": labels.get("k8s.deployment.name") or labels.get("k8s.statefulset.name") or labels.get("k8s.daemonset.name"),
                "service": metric.service,
                "metrics": {},
                "last_seen": None,
            },
        )
        current = item["metrics"].get(metric.metric_name)
        if not current or metric.timestamp > current["timestamp_raw"]:
            item["metrics"][metric.metric_name] = {
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat() if metric.timestamp else None,
                "timestamp_raw": metric.timestamp,
            }
            item["last_seen"] = metric.timestamp.isoformat() if metric.timestamp else item["last_seen"]
    return [
        {
            **{key: value for key, value in item.items() if key != "metrics"},
            "metrics": {key: {sub_key: sub_value for sub_key, sub_value in value.items() if sub_key != "timestamp_raw"} for key, value in item["metrics"].items()},
        }
        for item in groups.values()
    ]


@router.get("/traces/{trace_id}/detail")
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    trace_rows = (
        await db.execute(
            select(OtelTrace)
            .where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.trace_id == trace_id)
            .order_by(OtelTrace.start_time)
        )
    ).scalars().all()
    if not trace_rows:
        raise HTTPException(status_code=404, detail="Trace not found")
    span_rows = (
        await db.execute(
            select(OtelSpan)
            .where(OtelSpan.tenant_id == user.tenant_id, OtelSpan.trace_id == trace_id)
            .order_by(OtelSpan.start_time)
        )
    ).scalars().all()
    log_rows = (
        await db.execute(
            select(LogEntry)
            .where(LogEntry.tenant_id == user.tenant_id, LogEntry.trace_id == trace_id)
            .order_by(desc(LogEntry.timestamp))
            .limit(100)
        )
    ).scalars().all()
    rum_rows = (
        await db.execute(
            select(RumEvent)
            .where(RumEvent.tenant_id == user.tenant_id, RumEvent.trace_id == trace_id)
            .order_by(RumEvent.timestamp)
            .limit(100)
        )
    ).scalars().all()
    root = trace_rows[0]
    return {
        "trace": {
            "trace_id": root.trace_id,
            "service": root.service,
            "name": root.name,
            "status": root.status,
            "duration_ms": root.duration_ms,
            "method": root.method,
            "url": root.url,
            "response_code": root.response_code,
            "status_code": root.status_code,
            "kind": root.kind,
            "host_id": root.host_id,
            "host_name": root.host_name,
            "external_host": root.external_host,
            "external_service": root.external_service,
            "is_external_call": root.is_external_call,
            "start_time": root.start_time.isoformat() if root.start_time else None,
            "end_time": root.end_time.isoformat() if root.end_time else None,
            "attributes": root.attributes or {},
            "resource": root.resource or {},
            "events": root.events or [],
        },
        "flow": [
            {
                "span_id": trace.span_id,
                "parent_span_id": trace.parent_span_id,
                "service": trace.service,
                "name": trace.name,
                "kind": trace.kind,
                "status": trace.status,
                "method": trace.method,
                "response_code": trace.response_code,
                "duration_ms": trace.duration_ms,
                "url": trace.url,
                "host_name": trace.host_name,
                "attributes": trace.attributes or {},
                "resource": trace.resource or {},
                "events": trace.events or [],
            }
            for trace in trace_rows
        ],
        "spans": [
            {
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "service": span.service,
                "name": span.name,
                "status": span.status,
                "duration_ms": span.duration_ms,
                "attributes": span.attributes or {},
                "events": span.events or [],
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "end_time": span.end_time.isoformat() if span.end_time else None,
            }
            for span in span_rows
        ],
        "logs": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "source": log.source,
                "host_name": log.host_name,
                "service": log.service,
                "message": log.message,
            }
            for log in log_rows
        ],
        "rum_events": [
            {
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "application": event.application,
                "event_type": event.event_type,
                "name": event.name,
                "url": event.url,
                "duration_ms": event.duration_ms,
                "satisfied": event.satisfied,
            }
            for event in rum_rows
        ],
    }


@router.get("/services/detail")
async def get_service_detail(
    name: str = Query(...),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    traces = (
        await db.execute(
            select(OtelTrace)
            .where(
                OtelTrace.tenant_id == user.tenant_id,
                OtelTrace.service == name,
                OtelTrace.start_time >= range_start,
                OtelTrace.start_time <= range_end,
            )
            .order_by(desc(OtelTrace.start_time))
            .limit(200)
        )
    ).scalars().all()
    logs = (
        await db.execute(
            select(LogEntry)
            .where(LogEntry.tenant_id == user.tenant_id, LogEntry.service == name)
            .order_by(desc(LogEntry.timestamp))
            .limit(50)
        )
    ).scalars().all()
    urls: dict[str, int] = {}
    hosts: set[str] = set()
    for trace in traces:
        if trace.url:
            urls[trace.url] = urls.get(trace.url, 0) + 1
        if trace.host_name:
            hosts.add(trace.host_name)
    return {
        "name": name,
        "requests": len(traces),
        "errors": sum(1 for trace in traces if trace.status == "error" or (trace.response_code or 0) >= 500),
        "hosts": sorted(hosts),
        "urls": [{"url": url, "requests": count} for url, count in sorted(urls.items(), key=lambda item: item[1], reverse=True)[:50]],
        "traces": [
            {
                "trace_id": trace.trace_id,
                "name": trace.name,
                "status": trace.status,
                "duration_ms": trace.duration_ms,
                "url": trace.url,
                "start_time": trace.start_time.isoformat() if trace.start_time else None,
            }
            for trace in traces[:20]
        ],
        "logs": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "source": log.source,
                "message": log.message,
            }
            for log in logs
        ],
    }


@router.get("/applications/detail")
async def get_application_detail(
    name: str = Query(...),
    timeframe: str = Query("24h"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    range_start, range_end = parse_timeframe(timeframe, start, end)
    trace_rows = (
        await db.execute(
            select(OtelTrace)
            .where(OtelTrace.tenant_id == user.tenant_id, OtelTrace.start_time >= range_start, OtelTrace.start_time <= range_end)
            .order_by(desc(OtelTrace.start_time))
            .limit(1000)
        )
    ).scalars().all()
    traces = [trace for trace in trace_rows if infer_application_name(trace.url) == name]
    rum_events = (
        await db.execute(
            select(RumEvent)
            .where(
                RumEvent.tenant_id == user.tenant_id,
                RumEvent.application == name,
                RumEvent.timestamp >= range_start,
                RumEvent.timestamp <= range_end,
            )
            .order_by(desc(RumEvent.timestamp))
            .limit(200)
        )
    ).scalars().all()
    sessions = (
        await db.execute(
            select(RumSession)
            .where(
                RumSession.tenant_id == user.tenant_id,
                RumSession.application == name,
                RumSession.last_seen >= range_start,
                RumSession.last_seen <= range_end,
            )
            .order_by(desc(RumSession.last_seen))
            .limit(100)
        )
    ).scalars().all()
    return {
        "name": name,
        "has_rum": bool(sessions or rum_events),
        "message": None if sessions or rum_events else "Ainda nao temos sessoes RUM suficientes. Configure o monitoramento da experiencia do usuario para ver usuarios, sessoes, browser/OS e tempos client/server/network.",
        "requests": len(traces) + sum(1 for event in rum_events if event.event_type in {"request", "resource"}),
        "errors": sum(1 for trace in traces if trace.status == "error" or (trace.response_code or 0) >= 400) + sum(1 for event in rum_events if (event.status_code or 0) >= 400 or event.event_type in {"error", "javascript_error"}),
        "sessions": [
            {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "live": session.live,
                "last_seen": session.last_seen.isoformat() if session.last_seen else None,
                "satisfaction_index": session.satisfaction_index,
                "requests_total": session.requests_total,
                "actions_total": session.actions_total,
                "errors_total": session.errors_total,
            }
            for session in sessions
        ],
        "traces": [
            {
                "trace_id": trace.trace_id,
                "service": trace.service,
                "name": trace.name,
                "status": trace.status,
                "url": trace.url,
                "duration_ms": trace.duration_ms,
            }
            for trace in traces[:50]
        ],
        "rum_events": [
            {
                "event_type": event.event_type,
                "name": event.name,
                "url": event.url,
                "duration_ms": event.duration_ms,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            }
            for event in rum_events[:50]
        ],
    }


@router.get("/gateways")
async def list_gateways(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Gateway)
        .where(
            Gateway.tenant_id == user.tenant_id,
            not_(and_(
                Gateway.status == "pending_install",
                Gateway.last_heartbeat.is_(None),
                Gateway.config["provisioning_source"].as_string() == "installer_download",
            )),
        )
        .order_by(desc(Gateway.last_heartbeat), Gateway.name)
    )
    return [serialize_gateway(gateway) for gateway in result.scalars().all()]


@router.get("/gateways/topology")
async def gateway_topology(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routes = await resolve_gateway_routes(db, user.tenant_id)
    clusters: dict[str, dict] = {}
    for route in routes:
        cluster = clusters.setdefault(
            route["cluster_name"],
            {
                "cluster_name": route["cluster_name"],
                "primary": [],
                "failover": [],
                "shared": [],
            },
        )
        if route["tenant_scope"] == "shared":
            cluster["shared"].append(route)
        elif route["failover_only"]:
            cluster["failover"].append(route)
        else:
            cluster["primary"].append(route)
    return {
        "strategy": "priority-weighted-failover",
        "clusters": list(clusters.values()),
    }


@router.post("/gateways")
async def create_gateway(
    payload: GatewayCreatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    gateway = await create_gateway_token(
        db=db,
        tenant_id=user.tenant_id,
        name=payload.name,
        gateway_type=payload.type,
        host=payload.host or "0.0.0.0",
        port=payload.port,
        config={
            "priority": payload.priority,
            "weight": payload.weight,
            "cluster_name": payload.cluster_name,
            "failover_only": payload.failover_only,
            "shared_with_tenants": payload.shared_with_tenants,
            "public_endpoint": payload.public_endpoint,
            "transport": {
                "mtls_required": True,
                "compress_enabled": payload.compress_enabled,
                "encrypt_enabled": payload.encrypt_enabled,
            },
        },
    )
    gateway.tls_enabled = payload.tls_enabled or (payload.public_endpoint.startswith("https://") if payload.public_endpoint else True)
    gateway.compress_enabled = payload.compress_enabled
    gateway.encrypt_enabled = payload.encrypt_enabled
    await db.commit()
    return {
        "id": gateway.id,
        "status": "created",
        "token_preview": f"{gateway.token[:12]}...",
    }


@router.put("/gateways/{gateway_id}")
async def update_gateway(
    gateway_id: str,
    payload: GatewayUpdatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id, Gateway.tenant_id == user.tenant_id))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")

    if payload.name is not None:
        gateway.name = payload.name
    if payload.type is not None:
        gateway.type = payload.type
    if payload.host is not None:
        gateway.host = payload.host
    if payload.port is not None:
        gateway.port = payload.port

    config = dict(gateway.config or {})
    for key in ["priority", "weight", "cluster_name", "failover_only", "shared_with_tenants", "public_endpoint"]:
        value = getattr(payload, key)
        if value is not None:
            config[key] = value
    gateway.config = config

    if payload.tls_enabled is not None:
        gateway.tls_enabled = payload.tls_enabled
    if payload.compress_enabled is not None:
        gateway.compress_enabled = payload.compress_enabled
    if payload.encrypt_enabled is not None:
        gateway.encrypt_enabled = payload.encrypt_enabled

    await db.commit()
    return {"status": "saved", "gateway_id": gateway.id}


@router.delete("/gateways/{gateway_id}")
async def delete_gateway(
    gateway_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Gateway).where(Gateway.id == gateway_id, Gateway.tenant_id == user.tenant_id))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")
    await db.delete(gateway)
    await db.commit()
    return {"status": "deleted", "gateway_id": gateway_id}


@router.post("/gateways/cleanup")
async def cleanup_gateways(
    payload: GatewayCleanupPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Gateway).where(Gateway.tenant_id == user.tenant_id))
    gateways = result.scalars().all()
    deleted_ids: list[str] = []
    for gateway in gateways:
        gateway_status, _ = gateway_health(gateway)
        if payload.delete_offline_only and gateway_status not in {"offline", "stale"}:
            continue
        if gateway.name in payload.delete_names or any(gateway.name.startswith(prefix) for prefix in payload.delete_prefixes):
            deleted_ids.append(gateway.id)
            await db.delete(gateway)
    await db.commit()
    return {"status": "cleaned", "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.username)
    )
    return [
        {
            "id": row.id,
            "username": row.username,
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
            "active": row.active,
        }
        for row in result.scalars().all()
    ]


@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_settings = tenant.settings or {}
    theme = tenant_settings.get("theme", {})
    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "admin_name": tenant.admin_name,
            "admin_email": tenant.admin_email,
        },
        "settings": {
            "company_name": tenant_settings.get("company_name", "LAS"),
            "platform_name": tenant_settings.get("platform_name", settings.APP_NAME),
            "platform_url": tenant_settings.get("platform_url", settings.PLATFORM_URL),
            "public_web_url": tenant_settings.get("public_web_url", settings.PUBLIC_WEB_URL),
            "smtp_host": tenant_settings.get("smtp_host", settings.SMTP_HOST),
            "smtp_port": tenant_settings.get("smtp_port", settings.SMTP_PORT),
            "smtp_user": tenant_settings.get("smtp_user", settings.SMTP_USER),
            "smtp_from": tenant_settings.get("smtp_from", settings.SMTP_FROM),
            "ai_provider": clean_setting_value(tenant.ai_provider or settings.AI_PROVIDER, 50),
            "ai_model": clean_setting_value(tenant.ai_model or settings.OPENAI_MODEL, 50),
            "theme_primary": theme.get("primary", "#ff375f"),
            "theme_secondary": theme.get("secondary", "#18233a"),
            "theme_surface": theme.get("surface", "#0c1527"),
        },
    }


@router.put("/settings")
async def update_settings(
    payload: SettingsPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    current = dict(tenant.settings or {})
    current["company_name"] = payload.company_name
    current["platform_name"] = payload.platform_name
    current["platform_url"] = payload.platform_url
    current["public_web_url"] = payload.public_web_url
    current["smtp_host"] = payload.smtp_host
    current["smtp_port"] = payload.smtp_port
    current["smtp_user"] = payload.smtp_user
    current["smtp_from"] = payload.smtp_from
    current["theme"] = {
        "primary": payload.theme_primary or "#ff375f",
        "secondary": payload.theme_secondary or "#18233a",
        "surface": payload.theme_surface or "#0c1527",
    }
    tenant.settings = current
    flag_modified(tenant, "settings")
    tenant.ai_provider = clean_setting_value(payload.ai_provider, 50) or tenant.ai_provider
    tenant.ai_model = clean_setting_value(payload.ai_model, 50) or tenant.ai_model
    tenant.name = payload.company_name
    await db.commit()

    return {"status": "saved"}


@router.get("/settings/notification-channels")
async def list_notification_channels(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.tenant_id == user.tenant_id)
        .order_by(NotificationChannel.name)
    )
    return [
        {
            "id": channel.id,
            "name": channel.name,
            "type": channel.type,
            "enabled": channel.enabled,
            "config": channel.config or {},
            "last_status": channel.last_status,
        }
        for channel in result.scalars().all()
    ]


@router.post("/settings/notification-channels")
async def upsert_notification_channel(
    payload: NotificationChannelPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.tenant_id == user.tenant_id,
            NotificationChannel.name == payload.name,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        channel = NotificationChannel(
            id=str(uuid4()),
            tenant_id=user.tenant_id,
            name=payload.name,
            type=payload.type,
        )
        db.add(channel)

    channel.type = payload.type
    channel.enabled = payload.enabled
    channel.config = payload.config
    channel.last_status = "configured"
    await db.commit()

    return {"status": "saved"}
