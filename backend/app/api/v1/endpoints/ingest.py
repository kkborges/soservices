"""
Ingest API — Receives data from agents, gateways, OTel SDK and APM.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
from app.db.base import get_db
from app.models import AgentToken, Gateway, Host, HostMetric, IdsAlert, LogEntry, NetworkAsset, OtelTrace, OtelSpan, OtelMetric, RumEvent, RumSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
import uuid
import json
import base64
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from app.services.mtls_guard import require_mtls_request

router = APIRouter(prefix="/ingest", tags=["ingest"])
INT32_MAX = 2_147_483_647


async def read_otel_payload(request: Request, kind: str) -> Dict[str, Any]:
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()
    if "application/x-protobuf" in content_type or "application/protobuf" in content_type:
        message = ExportTraceServiceRequest() if kind == "traces" else ExportMetricsServiceRequest()
        message.ParseFromString(body)
        return MessageToDict(message, preserving_proto_field_name=False)
    if not body:
        return {"resourceSpans": []} if kind == "traces" else {"resourceMetrics": []}
    return json.loads(body.decode("utf-8"))


def safe_int32(value: Any) -> int | None:
    if value is None:
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if numeric > INT32_MAX:
        return INT32_MAX
    if numeric < -INT32_MAX - 1:
        return -INT32_MAX - 1
    return numeric


def safe_bigint(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_otel_id(value: Any) -> str:
    text = str(value or "")
    if all(char in "0123456789abcdefABCDEF" for char in text) and len(text) in {16, 32}:
        return text.lower()
    try:
        return base64.b64decode(text).hex()
    except Exception:
        return text


def normalize_otel_status_code(value: Any) -> int:
    if isinstance(value, str):
        mapped = {
            "STATUS_CODE_UNSET": 0,
            "STATUS_CODE_OK": 1,
            "STATUS_CODE_ERROR": 2,
        }.get(value.upper())
        if mapped is not None:
            return mapped
    return safe_int32(value) or 0


def normalize_interfaces(interfaces: Any, primary_ip: str | None = None, limit: int = 64) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(primary_ip, str) and primary_ip.strip():
        normalized.append({"name": "primary", "ip": primary_ip.strip(), "primary": True})
    if isinstance(interfaces, list):
        for item in interfaces[:limit]:
            if not isinstance(item, dict):
                continue
            ip = str(item.get("ip") or "").strip()
            if not ip:
                continue
            normalized.append(
                {
                    "name": str(item.get("name") or "")[:100] or None,
                    "ip": ip[:50],
                    "mac": str(item.get("mac") or "")[:100] or None,
                    "is_up": bool(item.get("is_up")) if item.get("is_up") is not None else None,
                    "primary": bool(item.get("primary")),
                }
            )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in normalized:
        ip = item.get("ip")
        if not ip or ip in seen:
            continue
        seen.add(ip)
        unique.append(item)
    return unique


def update_host_interfaces(host: Host, interfaces: Any, primary_ip: str | None = None) -> None:
    incoming = normalize_interfaces(interfaces, primary_ip)
    if not incoming:
        return
    config = dict(host.custom_config or {})
    existing = config.get("interfaces") if isinstance(config.get("interfaces"), list) else []
    by_ip = {str(item.get("ip")): dict(item) for item in existing if isinstance(item, dict) and item.get("ip")}
    for item in incoming:
        current = by_ip.get(item["ip"], {})
        current.update({key: value for key, value in item.items() if value is not None})
        by_ip[item["ip"]] = current
    config["interfaces"] = list(by_ip.values())[:128]
    config["known_ips"] = sorted(by_ip.keys())
    host.custom_config = config
    flag_modified(host, "custom_config")


def normalize_processes(processes: Any, limit: int = 25) -> list[dict[str, Any]]:
    if not isinstance(processes, list):
        return []
    normalized: list[dict[str, Any]] = []
    for proc in processes[:limit]:
        if not isinstance(proc, dict):
            continue
        normalized.append(
            {
                "pid": proc.get("pid"),
                "name": str(proc.get("name") or "unknown")[:255],
                "username": str(proc.get("username") or "")[:255] or None,
                "status": str(proc.get("status") or "")[:50] or None,
                "cpuUsage": float(proc.get("cpuUsage") or 0),
                "memoryUsage": float(proc.get("memoryUsage") or 0),
            }
        )
    return normalized


def update_host_process_snapshot(host: Host, processes: Any) -> None:
    normalized = normalize_processes(processes)
    if not normalized:
        return
    config = dict(host.custom_config or {})
    config["latest_processes"] = normalized
    config["latest_processes_at"] = datetime.now(timezone.utc).isoformat()
    host.custom_config = config
    flag_modified(host, "custom_config")


def update_host_log_discovery(host: Host, paths: Any) -> None:
    if not isinstance(paths, list):
        return
    normalized = sorted({str(path)[:500] for path in paths if path})
    if not normalized:
        return
    config = dict(host.custom_config or {})
    config["detected_log_paths"] = normalized[:50]
    config["detected_log_paths_at"] = datetime.now(timezone.utc).isoformat()
    host.custom_config = config
    flag_modified(host, "custom_config")


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


async def verify_agent_token(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AgentToken:
    """Verify Bearer token and return AgentToken record."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")

    token_str = authorization.replace("Bearer ", "").strip()
    result = await db.execute(
        select(AgentToken).where(
            AgentToken.token == token_str,
            AgentToken.active == True
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or revoked token")

    # Update last_used
    token.last_used = datetime.now(timezone.utc)
    await db.commit()
    return token


async def verify_gateway_token(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Gateway:
    """Verify Bearer token and return Gateway record."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")

    token_str = authorization.replace("Bearer ", "").strip()
    result = await db.execute(select(Gateway).where(Gateway.token == token_str))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=401, detail="Invalid gateway token")

    gateway.last_heartbeat = datetime.now(timezone.utc)
    gateway.status = "online"
    await db.commit()
    return gateway


async def get_or_create_host(
    db: AsyncSession,
    tenant_id: str,
    hostname: str,
    defaults: Optional[Dict[str, Any]] = None,
) -> Host:
    payload = defaults or {}
    ip = payload.get("ip")
    result = await db.execute(
        select(Host)
        .where(Host.tenant_id == tenant_id)
        .order_by(Host.last_seen.desc())
        .limit(500)
    )
    for host in result.scalars().all():
        known_ips = (host.custom_config or {}).get("known_ips") or []
        if host.hostname == hostname or (ip and (host.ip == ip or ip in known_ips)):
            update_host_interfaces(host, payload.get("interfaces"), ip)
            return host

    host = Host(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        hostname=hostname,
        ip=payload.get("ip"),
        os=payload.get("os"),
        os_version=payload.get("os_version"),
        kernel=payload.get("kernel"),
        arch=payload.get("arch"),
        manufacturer=payload.get("manufacturer"),
        model=payload.get("model"),
        agent_version=payload.get("agent_version"),
        monitoring_mode=payload.get("monitoring_mode", "infra+otel"),
        status="online",
        last_seen=datetime.now(timezone.utc),
    )
    update_host_interfaces(host, payload.get("interfaces"), payload.get("ip"))
    db.add(host)
    await db.flush()
    return host


async def store_logs(
    db: AsyncSession,
    tenant_id: str,
    host_id: Optional[str],
    logs: List[Dict[str, Any]],
) -> int:
    now = datetime.now(timezone.utc)
    created = 0
    for log_data in logs:
        resolved_host_id = host_id
        if not resolved_host_id:
            hostname = log_data.get("hostname")
            host_ip = log_data.get("ip")
            if hostname or host_ip:
                host_result = await db.execute(
                    select(Host.id)
                    .where(
                        Host.tenant_id == tenant_id,
                        (Host.hostname == hostname) | (Host.ip == host_ip),
                    )
                    .order_by(Host.last_seen.desc())
                    .limit(1)
                )
                resolved_host_id = host_result.scalar_one_or_none()
            if not resolved_host_id and host_ip and log_data.get("source") == "syslog":
                asset_result = await db.execute(
                    select(NetworkAsset).where(NetworkAsset.tenant_id == tenant_id, NetworkAsset.ip == host_ip).limit(1)
                )
                asset = asset_result.scalar_one_or_none()
                if not asset:
                    asset = NetworkAsset(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        ip=host_ip,
                        hostname=hostname or host_ip,
                        asset_type="unknown",
                        group="net_discovered",
                    )
                    db.add(asset)
                asset.hostname = hostname or asset.hostname or host_ip
                asset.syslog_enabled = True
                asset.syslog_port = int((log_data.get("fields") or {}).get("syslog_port") or 514)
                asset.status = "online"
                asset.last_scan = now

                host = Host(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    hostname=hostname or host_ip,
                    ip=host_ip,
                    monitoring_mode="syslog",
                    status="online",
                    last_seen=now,
                )
                db.add(host)
                await db.flush()
                resolved_host_id = host.id
        db.add(
            LogEntry(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                host_id=resolved_host_id,
                timestamp=parse_timestamp(log_data.get("timestamp") or now),
                level=log_data.get("level", "info"),
                source=log_data.get("source"),
                group=log_data.get("group", "general"),
                host_name=log_data.get("hostname"),
                host_ip=log_data.get("ip"),
                message=log_data.get("message", ""),
                raw=log_data.get("raw"),
                trace_id=log_data.get("traceId"),
                service=log_data.get("service"),
                parsed_fields=log_data.get("fields", {}),
            )
        )
        created += 1
    return created


async def store_host_metric_batch(
    db: AsyncSession,
    tenant_id: str,
    metric_points: List[Dict[str, Any]],
) -> int:
    created = 0
    now = datetime.now(timezone.utc)
    for point in metric_points:
        host = await get_or_create_host(
            db,
            tenant_id,
            point.get("hostname", "unknown-host"),
            defaults={
                "ip": point.get("ip"),
                "os": point.get("os"),
                "agent_version": point.get("agent_version"),
                "interfaces": point.get("interfaces"),
            },
        )
        metrics = point.get("metrics", {})
        host.status = "online"
        host.last_seen = now
        if not host.ip:
            host.ip = point.get("ip") or host.ip
        update_host_interfaces(host, point.get("interfaces"), point.get("ip"))
        host.cpu_usage = metrics.get("cpuUsage", host.cpu_usage)
        host.memory_usage = metrics.get("memoryUsage", host.memory_usage)
        host.disk_usage = metrics.get("diskUsage", host.disk_usage)
        host.uptime = point.get("uptime", host.uptime)
        host.os = point.get("os") or host.os
        host.os_version = point.get("os_version") or host.os_version
        host.kernel = point.get("kernel") or host.kernel
        host.arch = point.get("arch") or host.arch
        host.agent_version = point.get("agent_version") or host.agent_version
        host.cpu_cores = point.get("cpu_cores") or host.cpu_cores
        host.memory_total_mb = point.get("memory_total_mb") or host.memory_total_mb
        host.disk_total_gb = point.get("disk_total_gb") or host.disk_total_gb
        update_host_process_snapshot(host, point.get("processes"))
        update_host_log_discovery(host, point.get("detected_log_paths"))

        db.add(
            HostMetric(
                id=str(uuid.uuid4()),
                host_id=host.id,
                tenant_id=tenant_id,
                timestamp=parse_timestamp(point.get("timestamp") or now),
                cpu_usage=metrics.get("cpuUsage"),
                memory_usage=metrics.get("memoryUsage"),
                disk_usage=metrics.get("diskUsage"),
                load_avg_1=metrics.get("loadAvg1"),
                load_avg_5=metrics.get("loadAvg5"),
                load_avg_15=metrics.get("loadAvg15"),
                net_rx_bytes=safe_bigint(metrics.get("netRxBytes")),
                net_tx_bytes=safe_bigint(metrics.get("netTxBytes")),
                disk_read_bytes=safe_bigint(metrics.get("diskReadBytes")),
                disk_write_bytes=safe_bigint(metrics.get("diskWriteBytes")),
                processes_total=safe_int32(metrics.get("processesTotal")),
                processes_running=safe_int32(metrics.get("processesRunning")),
            )
        )
        created += 1
    return created


async def store_otel_traces(
    db: AsyncSession,
    tenant_id: str,
    data: Dict[str, Any],
) -> int:
    resource_spans = data.get("resourceSpans", [])
    created = 0

    for rs in resource_spans:
        resource = rs.get("resource", {})
        resource_attrs = {a["key"]: a.get("value", {}) for a in resource.get("attributes", [])}
        service_name = resource_attrs.get("service.name", {}).get("stringValue", "unknown")

        for scope_span in rs.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                trace_id = normalize_otel_id(span.get("traceId", ""))
                span_id = normalize_otel_id(span.get("spanId", ""))
                parent_id = normalize_otel_id(span.get("parentSpanId")) if span.get("parentSpanId") else None
                name = span.get("name", "")
                start_ns = int(span.get("startTimeUnixNano", 0))
                end_ns = int(span.get("endTimeUnixNano", 0))
                status = span.get("status", {})
                status_code_value = normalize_otel_status_code(status.get("code"))
                attrs = {a["key"]: a.get("value", {}) for a in span.get("attributes", [])}

                start_dt = parse_timestamp(start_ns / 1e9) if start_ns else datetime.now(timezone.utc)
                end_dt = parse_timestamp(end_ns / 1e9) if end_ns else None
                duration_ms = (end_ns - start_ns) / 1e6 if end_ns else None
                http_method = attrs.get("http.method", {}).get("stringValue")
                http_url = attrs.get("http.url", attrs.get("http.target", {})).get("stringValue")
                http_status = safe_int32(attrs.get("http.status_code", {}).get("intValue"))

                if not parent_id:
                    db.add(
                        OtelTrace(
                            id=str(uuid.uuid4()),
                            tenant_id=tenant_id,
                            trace_id=trace_id,
                            span_id=span_id,
                            parent_span_id=parent_id,
                            name=name,
                            service=service_name,
                            start_time=start_dt,
                            end_time=end_dt,
                            duration_ms=duration_ms,
                            status="error" if status_code_value == 2 else "ok",
                            status_code=status_code_value,
                            method=http_method,
                            url=http_url,
                            response_code=http_status,
                            attributes=attrs,
                            events=span.get("events", []),
                            resource=resource_attrs,
                            error_count=1 if status_code_value == 2 else 0,
                        )
                    )
                else:
                    db.add(
                        OtelSpan(
                            id=str(uuid.uuid4()),
                            trace_id=trace_id,
                            tenant_id=tenant_id,
                            span_id=span_id,
                            parent_span_id=parent_id,
                            name=name,
                            service=service_name,
                            start_time=start_dt,
                            end_time=end_dt,
                            duration_ms=duration_ms,
                            status="error" if status_code_value == 2 else "ok",
                            attributes=attrs,
                            events=span.get("events", []),
                        )
                    )
                created += 1
    return created


async def store_otel_metrics(
    db: AsyncSession,
    tenant_id: str,
    data: Dict[str, Any],
) -> int:
    resource_metrics = data.get("resourceMetrics", [])
    created = 0
    for rm in resource_metrics:
        resource = rm.get("resource", {})
        resource_attrs = {a["key"]: a.get("value", {}) for a in resource.get("attributes", [])}
        service_name = resource_attrs.get("service.name", {}).get("stringValue", "unknown")

        for scope_metric in rm.get("scopeMetrics", []):
            for metric in scope_metric.get("metrics", []):
                metric_name = metric.get("name")
                unit = metric.get("unit")
                data_points = (
                    metric.get("gauge", {}).get("dataPoints", []) or
                    metric.get("sum", {}).get("dataPoints", []) or
                    metric.get("histogram", {}).get("dataPoints", [])
                )

                for dp in data_points:
                    ts_ns = int(dp.get("timeUnixNano", 0))
                    ts = parse_timestamp(ts_ns / 1e9) if ts_ns else datetime.now(timezone.utc)
                    value = dp.get("asDouble") or dp.get("asInt") or dp.get("sum")
                    labels = {a["key"]: list(a.get("value", {}).values())[0] for a in dp.get("attributes", [])}
                    db.add(
                        OtelMetric(
                            id=str(uuid.uuid4()),
                            tenant_id=tenant_id,
                            service=service_name,
                            timestamp=ts,
                            metric_name=metric_name,
                            metric_type="gauge" if "gauge" in metric else "counter" if "sum" in metric else "histogram",
                            value=float(value) if value is not None else None,
                            unit=unit,
                            labels=labels,
                        )
                    )
                    created += 1
    return created


# ── Heartbeat & Metrics ────────────────────────────────────────────────────────

class HeartbeatPayload(BaseModel):
    hostname: str
    ip: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    kernel: Optional[str] = None
    arch: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    agent_version: Optional[str] = None
    uptime: Optional[int] = None
    cpu_cores: Optional[int] = None
    memory_total_mb: Optional[int] = None
    disk_total_gb: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    processes: Optional[List[Dict[str, Any]]] = None
    detected_log_paths: Optional[List[str]] = None
    interfaces: Optional[List[Dict[str, Any]]] = None


@router.post("/agent/heartbeat")
async def agent_heartbeat(
    request: Request,
    payload: HeartbeatPayload,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    now = datetime.now(timezone.utc)

    host = None
    if agent_token.bound_host_id:
        host = await db.get(Host, agent_token.bound_host_id)
        if host and host.tenant_id != agent_token.tenant_id:
            host = None

    if not host:
        host_result = await db.execute(
            select(Host)
            .where(Host.tenant_id == agent_token.tenant_id)
            .order_by(Host.last_seen.desc())
            .limit(500)
        )
        for candidate in host_result.scalars().all():
            known_ips = (candidate.custom_config or {}).get("known_ips") or []
            if candidate.hostname == payload.hostname or (payload.ip and (candidate.ip == payload.ip or payload.ip in known_ips)):
                host = candidate
                break

    if not host:
        # Auto-register new host
        host = Host(
            id=str(uuid.uuid4()),
            tenant_id=agent_token.tenant_id,
            hostname=payload.hostname,
            ip=payload.ip,
            os=payload.os,
            os_version=payload.os_version,
            kernel=payload.kernel,
            arch=payload.arch,
            manufacturer=payload.manufacturer,
            model=payload.model,
            agent_version=payload.agent_version,
            agent_token_id=agent_token.id,
            monitoring_mode="infra+otel",
        )
        db.add(host)
        await db.flush()

    agent_token.bound_host_id = host.id
    # Update host
    host.status = "online"
    host.last_seen = now
    if payload.ip:
        if not host.ip:
            host.ip = payload.ip
        elif host.ip != payload.ip:
            update_host_interfaces(host, payload.interfaces, payload.ip)
    if payload.agent_version:
        host.agent_version = payload.agent_version
    if payload.uptime:
        host.uptime = payload.uptime
    if payload.cpu_cores:
        host.cpu_cores = payload.cpu_cores
    if payload.memory_total_mb:
        host.memory_total_mb = payload.memory_total_mb
    if payload.disk_total_gb:
        host.disk_total_gb = payload.disk_total_gb

    # Update metrics snapshot
    metrics = payload.metrics or {}
    host.cpu_usage = metrics.get("cpuUsage", host.cpu_usage)
    host.memory_usage = metrics.get("memoryUsage", host.memory_usage)
    host.disk_usage = metrics.get("diskUsage", host.disk_usage)
    host.load_avg_1 = metrics.get("loadAvg1", host.load_avg_1)
    host.load_avg_5 = metrics.get("loadAvg5", host.load_avg_5)
    host.load_avg_15 = metrics.get("loadAvg15", host.load_avg_15)
    update_host_process_snapshot(host, payload.processes)
    update_host_log_discovery(host, payload.detected_log_paths)
    update_host_interfaces(host, payload.interfaces, payload.ip)

    # Store time-series metric point
    if metrics:
        metric = HostMetric(
            id=str(uuid.uuid4()),
            host_id=host.id,
            tenant_id=agent_token.tenant_id,
            timestamp=now,
            cpu_usage=metrics.get("cpuUsage"),
            memory_usage=metrics.get("memoryUsage"),
            disk_usage=metrics.get("diskUsage"),
            load_avg_1=metrics.get("loadAvg1"),
            load_avg_5=metrics.get("loadAvg5"),
            load_avg_15=metrics.get("loadAvg15"),
            net_rx_bytes=safe_bigint(metrics.get("netRxBytes")),
            net_tx_bytes=safe_bigint(metrics.get("netTxBytes")),
            disk_read_bytes=safe_bigint(metrics.get("diskReadBytes")),
            disk_write_bytes=safe_bigint(metrics.get("diskWriteBytes")),
            processes_total=safe_int32(metrics.get("processesTotal")),
            processes_running=safe_int32(metrics.get("processesRunning")),
        )
        db.add(metric)

    await db.commit()
    return {"status": "ok", "host_id": host.id, "interval": 60}


@router.get("/agent/ping")
async def agent_ping(request: Request, agent_token: AgentToken = Depends(verify_agent_token)):
    require_mtls_request(request)
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


class GatewayHeartbeatPayload(BaseModel):
    version: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    public_endpoint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/gateway/heartbeat")
async def gateway_heartbeat(
    request: Request,
    payload: GatewayHeartbeatPayload,
    gateway: Gateway = Depends(verify_gateway_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    if payload.version:
        gateway.version = payload.version
    if payload.host:
        gateway.host = payload.host
    if payload.port:
        gateway.port = payload.port

    merged_config = {
        **(gateway.config or {}),
        "last_metadata": payload.metadata or {},
    }
    if payload.public_endpoint:
        merged_config["public_endpoint"] = payload.public_endpoint
        gateway.tls_enabled = payload.public_endpoint.startswith("https://")
    if payload.metadata:
        for key in ["priority", "weight", "cluster_name", "failover_only", "shared_with_tenants"]:
            if key in payload.metadata:
                merged_config[key] = payload.metadata[key]
        if "heartbeat_interval" in payload.metadata:
            merged_config["heartbeat_interval"] = payload.metadata["heartbeat_interval"]
    if payload.port == 9443:
        gateway.tls_enabled = True
    gateway.config = merged_config
    gateway.status = "online"
    gateway.last_heartbeat = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "ok",
        "gateway_id": gateway.id,
        "timestamp": gateway.last_heartbeat.isoformat() if gateway.last_heartbeat else None,
    }


# ── IDS Alerts ─────────────────────────────────────────────────────────────────

class IdsAlertPayload(BaseModel):
    alerts: List[Dict[str, Any]]


@router.post("/ids")
async def ingest_ids_alerts(
    request: Request,
    payload: IdsAlertPayload,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    now = datetime.now(timezone.utc)
    created = 0

    for alert_data in payload.alerts:
        host_id = agent_token.bound_host_id

        alert = IdsAlert(
            id=str(uuid.uuid4()),
            tenant_id=agent_token.tenant_id,
            host_id=host_id,
            timestamp=now,
            severity=alert_data.get("severity", "medium"),
            attack_type=alert_data.get("attackType", "unknown"),
            category=alert_data.get("category"),
            source_ip=alert_data.get("sourceIp"),
            source_port=alert_data.get("sourcePort"),
            source_country=alert_data.get("sourceCountry"),
            dest_ip=alert_data.get("destIp"),
            dest_port=alert_data.get("destPort"),
            protocol=alert_data.get("protocol"),
            attempts=alert_data.get("attempts", 1),
            rule_id=alert_data.get("ruleId"),
            rule_name=alert_data.get("ruleName"),
            raw_log=alert_data.get("rawLog"),
            status="open",
        )
        db.add(alert)
        created += 1

    await db.commit()

    # Dispatch AI analysis for high-severity alerts
    if created > 0:
        from app.workers.security_worker import analyze_security_logs
        analyze_security_logs.apply_async(countdown=5)

    return {"status": "ok", "ingested": created}


# ── Logs ───────────────────────────────────────────────────────────────────────

class LogsPayload(BaseModel):
    logs: List[Dict[str, Any]]


@router.post("/logs")
async def ingest_logs(
    request: Request,
    payload: LogsPayload,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    created = await store_logs(db, agent_token.tenant_id, agent_token.bound_host_id, payload.logs)

    await db.commit()
    return {"status": "ok", "ingested": created}


class RumPayload(BaseModel):
    application: str
    session_id: str
    user_id: Optional[str] = None
    events: List[Dict[str, Any]] = []


@router.post("/rum/events")
async def ingest_rum_events(
    request: Request,
    payload: RumPayload,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    app_name = (payload.application or "unknown")[:255]
    session_id = (payload.session_id or str(uuid.uuid4()))[:100]
    result = await db.execute(
        select(RumSession).where(
            RumSession.tenant_id == agent_token.tenant_id,
            RumSession.session_id == session_id,
            RumSession.application == app_name,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        session = RumSession(
            id=str(uuid.uuid4()),
            tenant_id=agent_token.tenant_id,
            application=app_name,
            session_id=session_id,
            user_id=payload.user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            started_at=now,
            last_seen=now,
        )
        db.add(session)
    session.last_seen = now
    session.live = True
    if payload.user_id:
        session.user_id = payload.user_id[:255]

    created = 0
    errors = 0
    for event in payload.events[:100]:
        event_type = str(event.get("type") or event.get("event_type") or "action")[:50]
        status_code = safe_int32(event.get("status_code") or event.get("statusCode"))
        duration_ms = float(event.get("duration_ms") or event.get("duration") or 0)
        is_error = bool(event.get("error")) or (status_code is not None and status_code >= 400) or event_type in {"error", "javascript_error"}
        db.add(
            RumEvent(
                id=str(uuid.uuid4()),
                tenant_id=agent_token.tenant_id,
                application=app_name,
                session_id=session_id,
                event_type=event_type,
                name=str(event.get("name") or event.get("action") or event_type)[:500],
                url=str(event.get("url") or "")[:2000] or None,
                method=str(event.get("method") or "")[:20] or None,
                status_code=status_code,
                duration_ms=duration_ms,
                server_time_ms=float(event.get("server_time_ms") or 0) or None,
                network_time_ms=float(event.get("network_time_ms") or 0) or None,
                client_time_ms=float(event.get("client_time_ms") or 0) or None,
                trace_id=event.get("trace_id") or event.get("traceId"),
                span_id=event.get("span_id") or event.get("spanId"),
                service=event.get("service"),
                timestamp=parse_timestamp(event.get("timestamp") or now),
                satisfied=not is_error and duration_ms < float(event.get("satisfied_threshold_ms") or 3000),
                event_metadata=event,
            )
        )
        created += 1
        errors += 1 if is_error else 0

    session.requests_total = (session.requests_total or 0) + sum(1 for event in payload.events if str(event.get("type") or "").lower() in {"request", "resource"})
    session.actions_total = (session.actions_total or 0) + sum(1 for event in payload.events if str(event.get("type") or "action").lower() in {"action", "navigation", "click"})
    session.errors_total = (session.errors_total or 0) + errors
    total = max((session.requests_total or 0) + (session.actions_total or 0), 1)
    session.satisfaction_index = max(0, round(100 - ((session.errors_total or 0) / total) * 100, 2))

    await db.commit()
    return {"status": "ok", "events_ingested": created}


# ── OTel / APM ─────────────────────────────────────────────────────────────────

@router.post("/otel/traces")
async def ingest_otel_traces(
    request: Request,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    data = await read_otel_payload(request, "traces")
    created = await store_otel_traces(db, agent_token.tenant_id, data)

    await db.commit()
    return {"status": "ok", "spans_ingested": created}


@router.post("/otel/metrics")
async def ingest_otel_metrics(
    request: Request,
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    data = await read_otel_payload(request, "metrics")
    created = await store_otel_metrics(db, agent_token.tenant_id, data)

    await db.commit()
    return {"status": "ok", "metrics_ingested": created}


class GatewayBatchPayload(BaseModel):
    host_metrics: Optional[List[Dict[str, Any]]] = None
    logs: Optional[List[Dict[str, Any]]] = None
    traces: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None


@router.post("/gateway/batch")
async def ingest_gateway_batch(
    request: Request,
    payload: GatewayBatchPayload,
    gateway: Gateway = Depends(verify_gateway_token),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    tenant_id = gateway.tenant_id
    host_metric_count = await store_host_metric_batch(db, tenant_id, payload.host_metrics or [])
    log_count = await store_logs(db, tenant_id, None, payload.logs or [])
    trace_count = await store_otel_traces(db, tenant_id, payload.traces or {"resourceSpans": []})
    otel_metric_count = await store_otel_metrics(db, tenant_id, payload.metrics or {"resourceMetrics": []})
    gateway.last_heartbeat = datetime.now(timezone.utc)
    gateway.status = "online"
    await db.commit()

    return {
        "status": "ok",
        "host_metrics_ingested": host_metric_count,
        "logs_ingested": log_count,
        "trace_spans_ingested": trace_count,
        "otel_metrics_ingested": otel_metric_count,
    }
