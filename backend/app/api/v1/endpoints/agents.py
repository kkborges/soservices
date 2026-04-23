"""
Agent API — Download installers with auto-generated tokens.
GET /api/v1/agents/download/linux?role=agent&modules=infra,logs,otel
GET /api/v1/agents/download/windows
GET /api/v1/agents/download/docker
GET /api/v1/agents/download/k8s
GET /api/v1/agents/artifacts/{artifact}
POST /api/v1/agents/tokens  — create token manually
GET  /api/v1/agents/tokens  — list tokens
DELETE /api/v1/agents/tokens/{id}
"""
from pathlib import Path
import hashlib
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.services.gateway_routing import resolve_gateway_routes
from app.services.extension_metrics_service import store_extension_metrics
from app.services.license_service import (
    gateway_config_for_type,
    installer_options_payload,
    normalize_csv,
    resolve_agent_entitlements,
    resolve_gateway_type,
    tenant_license_codes,
)
from app.services.token_service import (
    create_agent_token, create_gateway_token, build_docker_compose,
    build_gateway_install_script, build_k8s_manifest,
    build_linux_install_script, build_windows_gateway_install_script, build_windows_install_script
)
from app.services.mtls_service import issue_agent_material, issue_gateway_material
from app.services.mtls_guard import require_mtls_request
from app.core.config import settings
from app.models import AgentToken, Gateway, Host, NetworkAsset, NetworkPort, Task, Tenant
from app.schemas.agent import AgentStatusUpdate, CreateAgentSchema
from sqlalchemy import desc, or_, select
from sqlalchemy.orm.attributes import flag_modified

router = APIRouter(prefix="/agents", tags=["agents"])
ROOT_DIR = Path(__file__).resolve().parents[4]
NETWORK_ASSET_TYPES = {"network", "switch", "router", "firewall", "ap", "hub", "access_point", "wifi", "wireless", "printer", "ups"}
HOST_DESCRIPTION_KEYWORDS = {
    "linux",
    "ubuntu",
    "debian",
    "red hat",
    "centos",
    "rocky",
    "alma",
    "windows",
    "microsoft",
    "vmware esxi",
    "freebsd",
}
NETWORK_DESCRIPTION_KEYWORDS = {
    "switch",
    "router",
    "firewall",
    "mikrotik",
    "routeros",
    "cisco",
    "juniper",
    "fortinet",
    "fortigate",
    "palo alto",
    "ubiquiti",
    "unifi",
    "aruba",
    "procurve",
    "hpe officeconnect",
    "tp-link",
    "tplink",
    "access point",
    "wireless",
    "gateway",
}
AGENT_ARTIFACTS = {
    "linux-agent.py": ROOT_DIR / "agents" / "shared" / "las_agent.py",
    "windows-agent.py": ROOT_DIR / "agents" / "shared" / "las_agent.py",
    "gateway.py": ROOT_DIR / "agents" / "shared" / "las_gateway.py",
    "linux-agent.bin": ROOT_DIR / "releases" / "las-agent-linux-x64.bin",
    "windows-agent.exe": ROOT_DIR / "releases" / "las-agent-windows-x64.exe",
    "LASAgentSetup.exe": ROOT_DIR / "releases" / "LASAgentSetup.exe",
    "linux-gateway.bin": ROOT_DIR / "releases" / "las-gateway-linux-x64.bin",
    "windows-gateway.exe": ROOT_DIR / "releases" / "las-gateway-windows-x64.exe",
    "LASGatewaySetup.exe": ROOT_DIR / "releases" / "LASGatewaySetup.exe",
}
SETUP_OVERLAY_MAGIC = b"LASSETUPCFG1"
COMPONENT_LATEST_VERSION = {
    "agent": "4.1.1",
    "gateway": "4.1.4",
}
COMPONENT_ARTIFACTS = {
    ("agent", "linux"): "linux-agent.bin",
    ("agent", "windows"): "windows-agent.exe",
    ("gateway", "linux"): "linux-gateway.bin",
    ("gateway", "windows"): "windows-gateway.exe",
}


class AgentUpdatePayload(BaseModel):
    """Payload for updating agent token metadata."""

    name: Optional[str] = None
    description: Optional[str] = None
    agent_type: Optional[str] = None
    status: Optional[str] = None
    hostname: Optional[str] = None
    version: Optional[str] = None


def serialize_agent_token(token: AgentToken) -> dict:
    config = token.install_config or {}
    return {
        "id": token.id,
        "name": token.name,
        "description": token.description,
        "agent_type": token.agent_type,
        "role": token.role,
        "status": token.status,
        "hostname": config.get("hostname"),
        "version": token.version,
        "tenant_id": token.tenant_id,
        "active": token.active,
        "last_heartbeat": token.last_heartbeat or token.last_used,
        "created_at": token.created_at,
        "updated_at": token.updated_at,
    }


async def current_tenant_or_404(db: AsyncSession, tenant_id: str) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def resolve_agent_install_request(
    db: AsyncSession,
    tenant_id: str,
    profile: str,
    modules: Optional[str],
) -> dict:
    tenant = await current_tenant_or_404(db, tenant_id)
    entitlements = resolve_agent_entitlements(
        tenant,
        profile=profile,
        requested_modules=normalize_csv(modules),
    )
    if entitlements.denied:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Modulo de monitoramento nao licenciado para este tenant",
                "denied_modules": entitlements.denied,
                "licenses": sorted(entitlements.licenses),
            },
        )
    module_set = set(entitlements.modules)
    return {
        "profile": entitlements.profile,
        "modules": entitlements.modules,
        "features": {
            "process_monitor": "processes" in module_set or "infra" in module_set,
            "service_monitor": "services" in module_set,
            "port_scan": "infra" in module_set,
            "disk_monitor": "infra" in module_set,
            "network_monitor": "infra" in module_set,
            "log_collection": True,
            "otel_enabled": "otel" in module_set or "traces" in module_set,
            "traces_enabled": "traces" in module_set,
            "rum_enabled": "rum" in module_set,
            "ids_enabled": "ids" in module_set,
            "vuln_scan_enabled": "vuln_scan" in module_set,
            "apm_enabled": "otel" in module_set or "traces" in module_set,
        },
        "licenses": sorted(entitlements.licenses),
    }


async def resolve_gateway_install_request(
    db: AsyncSession,
    tenant_id: str,
    gateway_type: str,
) -> dict:
    tenant = await current_tenant_or_404(db, tenant_id)
    licenses = tenant_license_codes(tenant)
    gateway_info = resolve_gateway_type(gateway_type)
    required_license = gateway_info.get("license", "infra")
    if required_license not in licenses:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Tipo de gateway nao licenciado para este tenant",
                "gateway_type": gateway_info["key"],
                "required_license": required_license,
                "licenses": sorted(licenses),
            },
        )
    config = gateway_config_for_type(gateway_info["key"])
    config["licenses"] = sorted(licenses)
    return {"info": gateway_info, "config": config}


def normalize_discovered_asset_type(item: dict) -> str:
    raw_type = (item.get("asset_type") or "unknown").lower()
    description = " ".join(
        str(item.get(field) or "")
        for field in ("manufacturer", "model", "os_firmware", "hostname")
    ).lower()
    if any(keyword in description for keyword in HOST_DESCRIPTION_KEYWORDS):
        if "windows" in description or "microsoft" in description:
            return "workstation"
        return "server"
    if any(keyword in description for keyword in NETWORK_DESCRIPTION_KEYWORDS):
        if any(keyword in description for keyword in {"firewall", "fortigate", "palo alto"}):
            return "firewall"
        if any(keyword in description for keyword in {"access point", "wireless", "unifi"}):
            return "ap"
        if any(keyword in description for keyword in {"router", "routeros", "mikrotik"}):
            return "router"
        return "switch"
    return raw_type


async def upsert_gateway_discovered_assets(db: AsyncSession, tenant_id: str, assets: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    for item in assets:
        ip = item.get("ip")
        if not ip:
            continue
        normalized_asset_type = normalize_discovered_asset_type(item)
        is_network_asset = normalized_asset_type in NETWORK_ASSET_TYPES
        if not is_network_asset:
            conditions = [Host.ip == ip]
            if item.get("hostname"):
                conditions.append(Host.hostname == item.get("hostname"))
            host_result = await db.execute(select(Host).where(Host.tenant_id == tenant_id, or_(*conditions)).order_by(desc(Host.agent_version), desc(Host.last_seen)))
            host = host_result.scalar_one_or_none()
            if not host:
                host = Host(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    ip=ip,
                    hostname=item.get("hostname") or ip,
                    monitoring_mode="discovered",
                )
                db.add(host)
            host.hostname = item.get("hostname") or host.hostname or ip
            config = dict(host.custom_config or {})
            interfaces = config.get("interfaces") if isinstance(config.get("interfaces"), list) else []
            known_ips = set(config.get("known_ips") or ([host.ip] if host.ip else []))
            known_ips.add(ip)
            if not any((entry or {}).get("ip") == ip for entry in interfaces if isinstance(entry, dict)):
                interfaces.append({"name": "discovered", "ip": ip, "primary": host.ip == ip})
            config["interfaces"] = interfaces[:128]
            config["known_ips"] = sorted(known_ips)
            host.custom_config = config
            flag_modified(host, "custom_config")
            if not host.ip:
                host.ip = ip
            host.status = "online"
            host.last_seen = now
            continue

        asset_id = item.get("id")
        asset = await db.get(NetworkAsset, asset_id) if asset_id else None
        if not asset:
            result = await db.execute(select(NetworkAsset).where(NetworkAsset.tenant_id == tenant_id, NetworkAsset.ip == ip))
            asset = result.scalar_one_or_none()
        if not asset:
            asset = NetworkAsset(id=str(uuid.uuid4()), tenant_id=tenant_id, ip=ip)
            db.add(asset)
        asset.hostname = item.get("hostname") or asset.hostname or ip
        asset.asset_type = normalized_asset_type or asset.asset_type or "unknown"
        asset.group = item.get("group") or asset.group or ("net_w_snmp" if item.get("snmp_enabled") else "net_discovered")
        asset.status = "online" if item.get("snmp_enabled") or item.get("features") else asset.status or "unknown"
        asset.last_scan = now
        if item.get("snmp_enabled") is not None:
            asset.snmp_enabled = bool(item.get("snmp_enabled"))
        if item.get("snmp_community"):
            asset.snmp_community = item.get("snmp_community")
        if item.get("syslog_enabled") is not None:
            asset.syslog_enabled = bool(item.get("syslog_enabled"))
        asset.manufacturer = item.get("manufacturer") or asset.manufacturer
        asset.model = item.get("model") or asset.model
        asset.os_firmware = item.get("os_firmware") or asset.os_firmware
        merged_features = set(asset.features or [])
        incoming_features = set(item.get("features") or [])
        if "udp:161" in incoming_features:
            merged_features.discard("tcp:161")
        asset.features = sorted({*merged_features, *incoming_features})
        if item.get("port_count") is not None:
            asset.port_count = int(item.get("port_count") or 0)
        else:
            asset.port_count = max(asset.port_count or 0, len(asset.features or []))
        ports = item.get("ports") or []
        if ports:
            existing_result = await db.execute(select(NetworkPort).where(NetworkPort.asset_id == asset.id))
            existing = {port.port_number: port for port in existing_result.scalars().all()}
            ports_up = 0
            ports_down = 0
            for port_item in ports:
                number = int(port_item.get("port_number") or 0)
                if number <= 0:
                    continue
                port = existing.get(number)
                if not port:
                    port = NetworkPort(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        asset_id=asset.id,
                        port_number=number,
                    )
                    db.add(port)
                port.name = port_item.get("name") or port.name
                port.description = port_item.get("description") or port.description
                port.media_type = port_item.get("media_type") or port.media_type
                port.speed_mbps = int(port_item.get("speed_mbps") or 0)
                port.status = port_item.get("status") or port.status
                port.rx_bytes = int(port_item.get("rx_bytes") or 0)
                port.tx_bytes = int(port_item.get("tx_bytes") or 0)
                port.rx_errors = int(port_item.get("rx_errors") or 0)
                port.tx_errors = int(port_item.get("tx_errors") or 0)
                port.last_updated = now
                if port.status == "up":
                    ports_up += 1
                elif port.status == "down":
                    ports_down += 1
            asset.ports_up = ports_up
            asset.ports_down = ports_down
            asset.ports_copper = sum(1 for port_item in ports if port_item.get("media_type") == "copper")
            asset.ports_fiber = sum(1 for port_item in ports if port_item.get("media_type") == "fiber")


def artifact_sha256(name: str) -> str | None:
    path = resolve_artifact_path(name)
    if not path or not path.exists() or path.is_dir():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def resolve_artifact_path(name: str) -> Path | None:
    """
    Prefer artifacts from ROOT_DIR/releases (prod), but fall back to ROOT_DIR/dist
    for dev/homolog environments where only dist outputs exist.
    """
    path = AGENT_ARTIFACTS.get(name)
    if not path:
        return None
    if path.exists():
        return path
    if path.parent.name == "releases":
        fallback = ROOT_DIR / "dist" / path.name
        if fallback.exists():
            return fallback
    return path


def normalize_os_name(os_name: str | None) -> str:
    value = (os_name or "").strip().lower()
    if value.startswith("win"):
        return "windows"
    return "linux"


async def resolve_gateway_urls(db: AsyncSession, tenant_id: str) -> list[str]:
    routes = await resolve_gateway_routes(db, tenant_id)
    return [route["url"] for route in routes]


def embed_setup_overlay(setup_name: str, overlay: dict) -> bytes:
    setup_path = resolve_artifact_path(setup_name)
    if not setup_path or not setup_path.exists():
        raise HTTPException(status_code=404, detail=f"{setup_name} not found")
    payload = json.dumps(overlay, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return setup_path.read_bytes() + payload + len(payload).to_bytes(8, "little") + SETUP_OVERLAY_MAGIC


async def verify_agent_token_value(
    authorization: Optional[str],
    db: AsyncSession,
) -> AgentToken:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token_value = authorization.replace("Bearer ", "").strip()
    result = await db.execute(
        select(AgentToken).where(
            AgentToken.token == token_value,
            AgentToken.active == True,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


async def verify_machine_token_value(
    authorization: Optional[str],
    db: AsyncSession,
) -> tuple[str, AgentToken | Gateway]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token_value = authorization.replace("Bearer ", "").strip()
    agent_result = await db.execute(
        select(AgentToken).where(
            AgentToken.token == token_value,
            AgentToken.active == True,
        )
    )
    agent = agent_result.scalar_one_or_none()
    if agent:
        return ("agent", agent)

    gateway_result = await db.execute(select(Gateway).where(Gateway.token == token_value))
    gateway = gateway_result.scalar_one_or_none()
    if gateway:
        return ("gateway", gateway)
    raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/install-options")
async def get_install_options(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    tenant = await current_tenant_or_404(db, user.tenant_id)
    return installer_options_payload(tenant)


@router.get("/download/linux", response_class=PlainTextResponse)
async def download_linux_installer(
    role: str = Query("agent"),
    format: str = Query("sh", pattern="^(sh|bin)$"),
    profile: str = Query("infra", pattern="^(infra|complete)$"),
    modules: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Auto-generates a token and returns the Linux bash installer.
    No manual token creation needed!
    """
    install_request = await resolve_agent_install_request(db, user.tenant_id, profile, modules)
    token = await create_agent_token(
        db=db,
        tenant_id=user.tenant_id,
        role=role,
        name=f"Linux Agent ({role})",
        description=f"Auto-generated on download by {user.username}",
        install_config={
            "os": "linux",
            "profile": install_request["profile"],
            "modules": install_request["modules"],
            "features": install_request["features"],
            "licenses": install_request["licenses"],
            "transport": {
                "mtls_required": True,
                "compress_enabled": True,
                "encrypt_enabled": True,
            },
        },
    )

    script = build_linux_install_script(
        platform_url=settings.PLATFORM_URL,
        token=token.token,
        role=role,
        modules=install_request["modules"],
        gateway_urls=await resolve_gateway_urls(db, user.tenant_id),
    )

    return PlainTextResponse(
        content=script,
        headers={
            "Content-Disposition": f"attachment; filename=install-las-agent-linux.{format}",
            "X-Token-ID": token.id,
        }
    )


@router.get("/download/windows")
async def download_windows_installer(
    role: str = Query("agent"),
    format: str = Query("exe", pattern="^(exe|ps1)$"),
    profile: str = Query("infra", pattern="^(infra|complete)$"),
    modules: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    install_request = await resolve_agent_install_request(db, user.tenant_id, profile, modules)
    token = await create_agent_token(
        db=db,
        tenant_id=user.tenant_id,
        role=role,
        name=f"Windows Agent ({role})",
        description=f"Auto-generated on download by {user.username}",
        install_config={
            "os": "windows",
            "profile": install_request["profile"],
            "modules": install_request["modules"],
            "features": install_request["features"],
            "licenses": install_request["licenses"],
            "transport": {
                "mtls_required": True,
                "compress_enabled": True,
                "encrypt_enabled": True,
            },
        },
    )

    gateway_urls = await resolve_gateway_urls(db, user.tenant_id)
    if format == "ps1":
        script = build_windows_install_script(
            platform_url=settings.PLATFORM_URL,
            token=token.token,
            role=role,
            modules=install_request["modules"],
            gateway_urls=gateway_urls,
            expected_sha256=artifact_sha256("windows-agent.exe"),
        )
        return PlainTextResponse(
            content=script,
            headers={
                "Content-Disposition": "attachment; filename=install-las-agent.ps1",
                "X-Token-ID": token.id,
            }
        )

    overlay = {
        "kind": "agent",
        "platform_url": settings.PLATFORM_URL,
        "mtls_platform_url": settings.MTLS_PLATFORM_URL,
        "token": token.token,
        "role": role,
        "profile": install_request["profile"],
        "modules": install_request["modules"],
        "features": install_request["features"],
        "gateway_urls": gateway_urls,
        "expected_sha256": artifact_sha256("windows-agent.exe") or "",
        "artifact_path": "/api/v1/agents/artifacts/windows-agent.exe",
        "mtls_bootstrap_path": "/api/v1/agents/bootstrap/mtls",
        "setup_name": "LASAgentSetup.exe",
        "payload_name": "las-agent.exe",
    }
    content = embed_setup_overlay("LASAgentSetup.exe", overlay)
    return Response(
        content=content,
        media_type="application/vnd.microsoft.portable-executable",
        headers={
            "Content-Disposition": "attachment; filename=LASAgentSetup.exe",
            "X-Token-ID": token.id,
        },
    )


@router.get("/routing")
async def get_agent_routing(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    token = await verify_agent_token_value(authorization, db)
    routes = await resolve_gateway_routes(db, token.tenant_id)
    return {
        "tenant_id": token.tenant_id,
        "strategy": "priority-weighted-failover",
        "refresh_interval_seconds": 300,
        "routes": routes,
    }


@router.get("/updates/check")
async def check_component_update(
    request: Request,
    kind: str = Query(..., pattern="^(agent|gateway)$"),
    version: str = Query("0.0.0"),
    os_name: str = Query("linux"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    machine_kind, machine = await verify_machine_token_value(authorization, db)
    if kind != machine_kind:
        raise HTTPException(status_code=403, detail="Token does not match component kind")

    normalized_os = normalize_os_name(os_name)
    artifact_name = COMPONENT_ARTIFACTS.get((kind, normalized_os))
    latest_version = COMPONENT_LATEST_VERSION[kind]
    if not artifact_name:
        raise HTTPException(status_code=404, detail="No update artifact for platform")

    artifact_path = resolve_artifact_path(artifact_name)
    if not artifact_path or not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Update artifact not found")

    sha256 = artifact_sha256(artifact_name)
    return {
        "kind": kind,
        "tenant_id": machine.tenant_id,
        "current_version": version,
        "latest_version": latest_version,
        "update_available": version != latest_version,
        "artifact": artifact_name,
        "artifact_path": f"/api/v1/agents/artifacts/{artifact_name}",
        "download_url": f"{settings.MTLS_PLATFORM_URL.rstrip('/')}/api/v1/agents/artifacts/{artifact_name}",
        "sha256": sha256,
        "strategy": "safe-replace-and-restart",
        "notes": "Validate sha256 before replacing the running payload.",
    }


@router.get("/bootstrap/mtls")
async def bootstrap_mtls_bundle(
    authorization: Optional[str] = Header(None),
    hostname: Optional[str] = Query(None),
    public_endpoint: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    machine_kind, machine = await verify_machine_token_value(authorization, db)
    if machine_kind == "agent":
        material = issue_agent_material(
            tenant_id=machine.tenant_id,
            token_id=machine.id,
            hostname=hostname or machine.bound_ip,
        )
        return {
            "kind": "agent",
            "mtls_required": settings.MTLS_REQUIRED,
            "mtls_platform_url": settings.MTLS_PLATFORM_URL,
            "ca_pem": material.ca_pem,
            "client_cert_pem": material.cert_pem,
            "client_key_pem": material.key_pem,
            "subject": material.subject,
            "serial": material.serial,
        }

    material = issue_gateway_material(
        tenant_id=machine.tenant_id,
        gateway_id=machine.id,
        hostname=hostname or machine.host,
        public_endpoint=public_endpoint or (machine.config or {}).get("public_endpoint"),
    )
    gateway_host = public_endpoint or (machine.config or {}).get("public_endpoint") or hostname or machine.host or ""
    return {
        "kind": "gateway",
        "mtls_required": settings.MTLS_REQUIRED,
        "mtls_platform_url": settings.MTLS_PLATFORM_URL,
        "gateway_public_endpoint": gateway_host,
        "ca_pem": material.ca_pem,
        "client_cert_pem": material.cert_pem,
        "client_key_pem": material.key_pem,
        "server_cert_pem": material.server_cert_pem,
        "server_key_pem": material.server_key_pem,
        "subject": material.subject,
        "serial": material.serial,
    }


@router.get("/gateway/tasks/next")
async def next_gateway_task(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    machine_kind, gateway = await verify_machine_token_value(authorization, db)
    if machine_kind != "gateway":
        raise HTTPException(status_code=403, detail="Gateway token required")
    result = await db.execute(
        select(Task)
        .where(
            Task.tenant_id == gateway.tenant_id,
            Task.status == "pending",
            Task.type.in_(["network_scan", "snmp_discovery", "snmp_get", "extension_collect"]),
        )
        .order_by(Task.scheduled_at, Task.created_at)
        .limit(20)
    )
    for task in result.scalars().all():
        task_result = task.result or {}
        if not task_result.get("gateway_execution"):
            continue
        assigned_gateway_id = task_result.get("gateway_id")
        if assigned_gateway_id and assigned_gateway_id != gateway.id:
            continue
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.progress = 5
        task_result["gateway_id"] = gateway.id
        task_result["gateway_name"] = gateway.name
        task.result = task_result
        flag_modified(task, "result")
        await db.commit()
        return {
            "task": {
                "id": task.id,
                "type": task.type,
                "target": task.target,
                "command": task_result.get("command") or {},
            }
        }
    return {"task": None}


@router.post("/gateway/tasks/{task_id}/result")
async def gateway_task_result(
    task_id: str,
    payload: dict,
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    require_mtls_request(request)
    machine_kind, gateway = await verify_machine_token_value(authorization, db)
    if machine_kind != "gateway":
        raise HTTPException(status_code=403, detail="Gateway token required")
    task = await db.get(Task, task_id)
    if not task or task.tenant_id != gateway.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    task_result = dict(task.result or {})
    if task_result.get("gateway_id") not in {None, gateway.id}:
        raise HTTPException(status_code=403, detail="Task assigned to another gateway")

    status = payload.get("status", "completed")
    result_payload = payload.get("result") or {}
    if result_payload.get("assets"):
        await upsert_gateway_discovered_assets(db, gateway.tenant_id, result_payload.get("assets") or [])
    elif task.type == "snmp_get" and result_payload.get("reachable"):
        command = task_result.get("command") or {}
        value = result_payload.get("value") or ""
        await upsert_gateway_discovered_assets(
            db,
            gateway.tenant_id,
            [
                {
                    "ip": result_payload.get("ip") or command.get("ip") or task.target,
                    "hostname": result_payload.get("ip") or command.get("ip") or task.target,
                    "asset_type": "network",
                    "group": "net_w_snmp",
                    "snmp_enabled": True,
                    "snmp_community": result_payload.get("community") or command.get("snmp_community"),
                    "manufacturer": value.split()[0] if isinstance(value, str) and value else None,
                    "model": value[:100] if isinstance(value, str) else None,
                    "os_firmware": value[:100] if isinstance(value, str) else None,
                    "features": [f"udp:{result_payload.get('port') or command.get('snmp_port') or 161}"],
                }
            ],
        )
    elif task.type == "extension_collect":
        # Gateway executed an extension inside the customer network; store metrics server-side.
        instance_id = (task_result.get("command") or {}).get("instance_id") or (result_payload.get("instance_id") if isinstance(result_payload, dict) else None)
        metrics = (result_payload.get("metrics") if isinstance(result_payload, dict) else None) or {}
        error_message = payload.get("error") or result_payload.get("error") if isinstance(result_payload, dict) else None
        try:
            await store_extension_metrics(
                db=db,
                tenant_id=gateway.tenant_id,
                instance_id=instance_id,
                source=str((task_result.get("command") or {}).get("extension_slug") or (result_payload.get("extension_slug") if isinstance(result_payload, dict) else "extension")),
                metrics=metrics,
                status=status if status in {"completed", "failed"} else "completed",
                error=error_message,
            )
        except Exception:
            # Do not fail the task result persistence due to metric parsing issues.
            pass

    task.status = status if status in {"completed", "failed", "cancelled"} else "completed"
    task.completed_at = datetime.now(timezone.utc)
    task.progress = 100 if task.status == "completed" else task.progress
    task.error = payload.get("error")
    task_result["gateway_id"] = gateway.id
    task_result["gateway_name"] = gateway.name
    task_result["gateway_result"] = result_payload
    task.result = task_result
    flag_modified(task, "result")
    await db.commit()
    return {"status": "saved"}


@router.get("/download/gateway/linux", response_class=PlainTextResponse)
async def download_linux_gateway_installer(
    gateway_type: str = Query("agents"),
    name: Optional[str] = Query(None),
    format: str = Query("sh", pattern="^(sh|bin)$"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    install_request = await resolve_gateway_install_request(db, user.tenant_id, gateway_type)
    gateway_info = install_request["info"]
    gateway_config = install_request["config"]
    gateway = await create_gateway_token(
        db=db,
        tenant_id=user.tenant_id,
        name=name or gateway_info["label"],
        gateway_type=gateway_info["key"],
        port=9443,
        config={
            **gateway_config,
            "provisioning_source": "installer_download",
            "installer_os": "linux",
            "priority": 100,
            "weight": 1,
            "cluster_name": "default",
            "failover_only": False,
            "shared_with_tenants": False,
            "transport": {
                "mtls_required": True,
                "compress_enabled": True,
                "encrypt_enabled": True,
            },
        },
        reuse_pending=True,
    )

    script = build_gateway_install_script(
        platform_url=settings.PLATFORM_URL,
        token=gateway.token,
        gateway_type=gateway.type,
        gateway_config=gateway.config,
    )

    return PlainTextResponse(
        content=script,
        headers={
            "Content-Disposition": f"attachment; filename=install-las-gateway-linux.{format}",
            "X-Gateway-ID": gateway.id,
        },
    )


@router.get("/download/gateway/windows")
async def download_windows_gateway_installer(
    gateway_type: str = Query("agents"),
    name: Optional[str] = Query(None),
    format: str = Query("exe", pattern="^(exe|ps1)$"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    install_request = await resolve_gateway_install_request(db, user.tenant_id, gateway_type)
    gateway_info = install_request["info"]
    gateway_config = install_request["config"]
    gateway = await create_gateway_token(
        db=db,
        tenant_id=user.tenant_id,
        name=name or f"{gateway_info['label']} Windows",
        gateway_type=gateway_info["key"],
        port=9443,
        config={
            **gateway_config,
            "provisioning_source": "installer_download",
            "installer_os": "windows",
            "priority": 100,
            "weight": 1,
            "cluster_name": "default",
            "failover_only": False,
            "shared_with_tenants": False,
            "transport": {
                "mtls_required": True,
                "compress_enabled": True,
                "encrypt_enabled": True,
            },
        },
        reuse_pending=True,
    )

    if format == "ps1":
        script = build_windows_gateway_install_script(
            platform_url=settings.PLATFORM_URL,
            token=gateway.token,
            gateway_type=gateway.type,
            gateway_config=gateway.config,
        )
        return PlainTextResponse(
            content=script,
            headers={
                "Content-Disposition": "attachment; filename=install-las-gateway.ps1",
                "X-Gateway-ID": gateway.id,
            },
        )

    overlay = {
        "kind": "gateway",
        "platform_url": settings.PLATFORM_URL,
        "mtls_platform_url": settings.MTLS_PLATFORM_URL,
        "token": gateway.token,
        "gateway_type": gateway.type,
        "gateway_config": gateway.config,
        "expected_sha256": artifact_sha256("windows-gateway.exe") or "",
        "artifact_path": "/api/v1/agents/artifacts/windows-gateway.exe",
        "mtls_bootstrap_path": "/api/v1/agents/bootstrap/mtls",
        "setup_name": "LASGatewaySetup.exe",
        "payload_name": "las-gateway.exe",
    }
    content = embed_setup_overlay("LASGatewaySetup.exe", overlay)
    return Response(
        content=content,
        media_type="application/vnd.microsoft.portable-executable",
        headers={
            "Content-Disposition": "attachment; filename=LASGatewaySetup.exe",
            "X-Gateway-ID": gateway.id,
        },
    )


@router.get("/download/docker", response_class=PlainTextResponse)
async def download_docker_compose(
    profile: str = Query("infra", pattern="^(infra|complete)$"),
    modules: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    install_request = await resolve_agent_install_request(db, user.tenant_id, profile, modules)
    token = await create_agent_token(
        db=db,
        tenant_id=user.tenant_id,
        role="agent",
        name="Docker Agent",
        description=f"Auto-generated for Docker by {user.username}",
        install_config={
            "os": "docker",
            "profile": install_request["profile"],
            "modules": install_request["modules"],
            "features": install_request["features"],
            "licenses": install_request["licenses"],
        },
    )

    script = build_docker_compose(
        platform_url=settings.PLATFORM_URL,
        token=token.token,
        role="agent",
        modules=install_request["modules"],
        gateway_urls=await resolve_gateway_urls(db, user.tenant_id),
    )

    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": "attachment; filename=docker-compose.las-agent.yml"}
    )


@router.get("/download/k8s", response_class=PlainTextResponse)
async def download_k8s_manifest(
    profile: str = Query("infra", pattern="^(infra|complete)$"),
    modules: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    install_request = await resolve_agent_install_request(db, user.tenant_id, profile, modules)
    token = await create_agent_token(
        db=db,
        tenant_id=user.tenant_id,
        role="k8s",
        name="Kubernetes DaemonSet Agent",
        description=f"Auto-generated for K8s by {user.username}",
        install_config={
            "os": "kubernetes",
            "profile": install_request["profile"],
            "modules": install_request["modules"],
            "features": install_request["features"],
            "licenses": install_request["licenses"],
        },
    )

    manifest = build_k8s_manifest(
        platform_url=settings.PLATFORM_URL,
        token=token.token,
        role="k8s",
        modules=install_request["modules"],
        gateway_urls=await resolve_gateway_urls(db, user.tenant_id),
    )

    return PlainTextResponse(
        content=manifest,
        headers={"Content-Disposition": "attachment; filename=las-agent-daemonset.yaml"}
    )


@router.get("/download/otel-config", response_class=PlainTextResponse)
async def download_otel_config(
    service_name: Optional[str] = Query(None),
    language: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns OpenTelemetry SDK configuration with auto-generated token.
    Supports: java, python, nodejs, dotnet, go, ruby.
    """
    from app.services.token_service import get_or_create_otel_token

    token = await get_or_create_otel_token(db, user.tenant_id, service_name)

    otel_endpoint = f"{settings.MTLS_PLATFORM_URL.rstrip('/')}/api/v1/ingest/otel"
    otel_host = settings.MTLS_PLATFORM_URL.replace("http://", "").replace("https://", "").rstrip("/")

    configs = {
        "python": f"""# OTel SDK — Python (auto-configured)
# pip install opentelemetry-sdk opentelemetry-exporter-otlp
# Requer certificado cliente mTLS emitido pela plataforma.

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource(attributes={{
    "service.name": "{service_name or 'my-service'}",
    "las.token": "{token.token}",
}})

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(
    endpoint="{otel_endpoint}/traces",
    headers={{"Authorization": "Bearer {token.token}"}},
    certificate_file="/etc/las/mtls-ca.pem",
    client_certificate_file="/etc/las/mtls-client.pem",
    client_key_file="/etc/las/mtls-client-key.pem",
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
""",
        "nodejs": f"""// OTel SDK — Node.js (auto-configured)
// npm install @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http

const {{ NodeSDK }} = require('@opentelemetry/sdk-node');
const {{ OTLPTraceExporter }} = require('@opentelemetry/exporter-trace-otlp-http');
const {{ Resource }} = require('@opentelemetry/resources');

const sdk = new NodeSDK({{
  resource: new Resource({{
    'service.name': '{service_name or 'my-service'}',
    'las.token': '{token.token}',
  }}),
  traceExporter: new OTLPTraceExporter({{
    url: '{otel_endpoint}/traces',
    headers: {{ Authorization: 'Bearer {token.token}' }},
  }}),
}});
sdk.start();
""",
        "java": f"""# OTel Agent — Java (auto-configured)
# Download: https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases

# Run your app with:
java -javaagent:opentelemetry-javaagent.jar \\
     -Dotel.service.name={service_name or 'my-service'} \\
     -Dotel.exporter.otlp.endpoint={otel_endpoint} \\
     -Dotel.exporter.otlp.headers="Authorization=Bearer {token.token}" \\
     -Dotel.exporter.otlp.certificate=/etc/las/mtls-ca.pem \\
     -Dotel.exporter.otlp.client.certificate=/etc/las/mtls-client.pem \\
     -Dotel.exporter.otlp.client.key=/etc/las/mtls-client-key.pem \\
     -jar your-app.jar
""",
        "dotnet": f"""# OTel SDK — .NET (auto-configured)
# dotnet add package OpenTelemetry.Extensions.Hosting
# dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol

builder.Services.AddOpenTelemetry()
    .WithTracing(tracer => tracer
        .SetResourceBuilder(ResourceBuilder.CreateDefault()
            .AddService("{service_name or 'my-service'}"))
        .AddOtlpExporter(opts => {{
            opts.Endpoint = new Uri("{otel_endpoint}/traces");
            opts.Headers = "Authorization=Bearer {token.token}";
        }}));
""",
        "go": f"""// OTel SDK — Go (auto-configured)
// go get go.opentelemetry.io/otel go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp

import (
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

exporter, _ := otlptracehttp.New(ctx,
    otlptracehttp.WithEndpoint("{otel_host}"),
    otlptracehttp.WithURLPath("/api/v1/ingest/otel/traces"),
    otlptracehttp.WithHeaders(map[string]string{{
        "Authorization": "Bearer {token.token}",
    }}),
)
tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exporter))
otel.SetTracerProvider(tp)
""",
    }

    if language == "auto":
        # Return all configs
        content = f"# OTel Token: {token.token}\n# Endpoint: {otel_endpoint}\n\n"
        content += "\n\n".join([f"## {lang.upper()}\n{code}" for lang, code in configs.items()])
    else:
        content = configs.get(language, configs["python"])

    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=las-otel-{language}.txt"}
    )


@router.get("/download/otel-installer", response_class=PlainTextResponse)
async def download_otel_installer(
    appname: str = Query("my-service"),
    language: str = Query("java"),
    host: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Download a portable helper that receives --host/--appname and prints an OTel bootstrap plan."""
    from app.services.token_service import get_or_create_otel_token

    token = await get_or_create_otel_token(db, user.tenant_id, appname)
    endpoint = f"{settings.MTLS_PLATFORM_URL.rstrip('/')}/api/v1/ingest/otel"
    script = f"""#!/usr/bin/env bash
set -euo pipefail

APPNAME="{appname}"
LANGUAGE="{language}"
HOST="{host or ''}"
ENDPOINT="{endpoint}"
TOKEN="{token.token}"
CERT_DIR="${{LAS_CERT_DIR:-/etc/las}}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --appname) APPNAME="$2"; shift 2 ;;
    --language) LANGUAGE="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --cert-dir) CERT_DIR="$2"; shift 2 ;;
    *) echo "Parametro desconhecido: $1"; exit 2 ;;
  esac
done

echo "LAS OpenTelemetry bootstrap"
echo "App: $APPNAME"
echo "Host: ${{HOST:-auto}}"
echo "Language: $LANGUAGE"
echo "Endpoint: $ENDPOINT"
echo

case "$LANGUAGE" in
  java)
    echo "Baixando opentelemetry-javaagent.jar se necessario..."
    curl -fsSL -o opentelemetry-javaagent.jar https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar
    cat <<JAVA
java -javaagent:opentelemetry-javaagent.jar \\
  -Dotel.service.name=$APPNAME \\
  -Dotel.resource.attributes=host.name=${{HOST:-$(hostname)}} \\
  -Dotel.exporter.otlp.endpoint=$ENDPOINT \\
  -Dotel.exporter.otlp.headers="Authorization=Bearer $TOKEN" \\
  -Dotel.exporter.otlp.certificate=$CERT_DIR/mtls-ca.pem \\
  -Dotel.exporter.otlp.client.certificate=$CERT_DIR/mtls-client.pem \\
  -Dotel.exporter.otlp.client.key=$CERT_DIR/mtls-client-key.pem \\
  -jar sua-aplicacao.jar
JAVA
    ;;
  nodejs|javascript|typescript)
    cat <<NODE
npm install @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-http
export OTEL_SERVICE_NAME="$APPNAME"
export OTEL_EXPORTER_OTLP_ENDPOINT="$ENDPOINT"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer $TOKEN"
export NODE_OPTIONS="--require @opentelemetry/auto-instrumentations-node/register"
node app.js
NODE
    ;;
  python)
    cat <<PY
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install
OTEL_SERVICE_NAME="$APPNAME" \\
OTEL_EXPORTER_OTLP_ENDPOINT="$ENDPOINT" \\
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer $TOKEN" \\
opentelemetry-instrument python app.py
PY
    ;;
  dotnet|csharp)
    cat <<DOTNET
export OTEL_SERVICE_NAME="$APPNAME"
export OTEL_EXPORTER_OTLP_ENDPOINT="$ENDPOINT"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer $TOKEN"
dotnet sua-aplicacao.dll
DOTNET
    ;;
  *)
    echo "Linguagem ainda sem instalador automatizado. Baixe /api/v1/agents/download/otel-config?language=auto"
    ;;
esac
"""
    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": "attachment; filename=las-otel-install.sh"},
    )


@router.get("/download/rum-js", response_class=PlainTextResponse)
async def download_rum_js(
    appname: str = Query("web-app"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.services.token_service import create_agent_token

    token = await create_agent_token(
        db=db,
        tenant_id=user.tenant_id,
        role="rum",
        name=f"RUM Token - {appname}",
        description=f"Auto-generated RUM token by {user.username}",
        install_config={"application": appname},
    )
    endpoint = f"{settings.PLATFORM_URL.rstrip('/')}/api/v1/ingest/rum/events"
    script = f"""(() => {{
  const app = "{appname}";
  const endpoint = "{endpoint}";
  const token = "{token.token}";
  const sessionKey = "las_rum_session_id";
  const session = localStorage.getItem(sessionKey) || (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
  localStorage.setItem(sessionKey, session);
  const send = (events) => navigator.sendBeacon
    ? navigator.sendBeacon(endpoint, new Blob([JSON.stringify({{ application: app, session_id: session, events }})], {{ type: "application/json" }}))
    : fetch(endpoint, {{ method: "POST", keepalive: true, headers: {{ "Content-Type": "application/json", Authorization: "Bearer " + token }}, body: JSON.stringify({{ application: app, session_id: session, events }}) }}).catch(() => null);
  const emit = (event) => fetch(endpoint, {{ method: "POST", keepalive: true, headers: {{ "Content-Type": "application/json", Authorization: "Bearer " + token }}, body: JSON.stringify({{ application: app, session_id: session, events: [event] }}) }}).catch(() => null);
  window.addEventListener("load", () => {{
    const nav = performance.getEntriesByType("navigation")[0];
    if (nav) emit({{ type: "navigation", name: document.title || location.pathname, url: location.href, duration_ms: nav.duration, network_time_ms: nav.responseStart - nav.requestStart, server_time_ms: nav.responseEnd - nav.requestStart, client_time_ms: nav.loadEventEnd - nav.responseEnd, timestamp: new Date().toISOString() }});
  }});
  window.addEventListener("error", (e) => emit({{ type: "javascript_error", name: e.message, url: location.href, timestamp: new Date().toISOString(), metadata: {{ filename: e.filename, lineno: e.lineno, colno: e.colno }} }}));
  window.addEventListener("click", (e) => emit({{ type: "click", name: (e.target && (e.target.innerText || e.target.id || e.target.tagName)) || "click", url: location.href, timestamp: new Date().toISOString() }}), true);
  const originalFetch = window.fetch;
  window.fetch = async (...args) => {{
    const started = performance.now();
    try {{
      const response = await originalFetch(...args);
      emit({{ type: "request", method: (args[1] && args[1].method) || "GET", url: String(args[0]), status_code: response.status, duration_ms: performance.now() - started, timestamp: new Date().toISOString() }});
      return response;
    }} catch (error) {{
      emit({{ type: "request", url: String(args[0]), error: true, name: String(error), duration_ms: performance.now() - started, timestamp: new Date().toISOString() }});
      throw error;
    }}
  }};
}})();
"""
    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": "attachment; filename=las-rum.js"},
    )


@router.get("/artifacts/{artifact_name}")
async def download_artifact(
    artifact_name: str,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")

    token_value = authorization.replace("Bearer ", "").strip()
    agent_result = await db.execute(select(AgentToken).where(AgentToken.token == token_value, AgentToken.active == True))
    gateway_result = await db.execute(select(Gateway).where(Gateway.token == token_value))
    if not agent_result.scalar_one_or_none() and not gateway_result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Invalid token")

    artifact_path = resolve_artifact_path(artifact_name)
    if not artifact_path or not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    if artifact_path.suffix in {".bin", ".exe"}:
        return FileResponse(
            artifact_path,
            filename=artifact_name,
            media_type="application/octet-stream",
        )

    content = artifact_path.read_text(encoding="utf-8")
    return PlainTextResponse(content=content, headers={"Content-Disposition": f"attachment; filename={artifact_name}"})


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: CreateAgentSchema,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = AgentToken(
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        agent_type=payload.agent_type,
        install_config={
            "hostname": payload.hostname,
            "os_type": payload.os_type,
            "status": "offline",
        },
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return serialize_agent_token(token)


@router.get("")
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=1000),
    agent_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(AgentToken).where(AgentToken.tenant_id == user.tenant_id, AgentToken.active == True)
    if agent_type:
        query = query.where(AgentToken.role == agent_type)
    total_rows = (await db.execute(query)).scalars().all()
    result = await db.execute(query.order_by(desc(AgentToken.created_at)).offset(skip).limit(limit))
    items = [serialize_agent_token(token) for token in result.scalars().all()]
    return {"items": items, "total": len(total_rows), "skip": skip, "limit": limit}


@router.post("/heartbeat", status_code=status.HTTP_202_ACCEPTED)
async def agent_heartbeat(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    agent_id = payload.get("agent_id") or payload.get("id")
    if ("agent_id" in payload or "id" in payload) and not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    if agent_id:
        token = await db.get(AgentToken, agent_id)
        if token:
            token.last_used = datetime.now(timezone.utc)
            token.status = "online"
            await db.commit()
    return {"status": "accepted"}


@router.get("/tokens")
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(AgentToken).where(AgentToken.tenant_id == user.tenant_id)
        .order_by(AgentToken.created_at.desc())
    )
    tokens = result.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "role": t.role,
            "active": t.active,
            "token_preview": t.token[:12] + "...",
            "last_used": t.last_used,
            "created_at": t.created_at,
            "expires_at": t.expires_at,
        }
        for t in tokens
    ]


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = await db.get(AgentToken, token_id)
    if not token or token.tenant_id != user.tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Token not found")
    token.active = False
    await db.commit()
    return {"status": "revoked"}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = await db.get(AgentToken, agent_id)
    if not token or token.tenant_id != user.tenant_id or not token.active:
        raise HTTPException(status_code=404, detail="Agent not found")
    return serialize_agent_token(token)


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    payload: AgentUpdatePayload,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = await db.get(AgentToken, agent_id)
    if not token or token.tenant_id != user.tenant_id or not token.active:
        raise HTTPException(status_code=404, detail="Agent not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        token.name = updates["name"]
    if "description" in updates:
        token.description = updates["description"]
    if "agent_type" in updates:
        token.agent_type = updates["agent_type"]
    config = dict(token.install_config or {})
    for key in ("status", "hostname", "version"):
        if key in updates:
            config[key] = updates[key]
    token.install_config = config
    flag_modified(token, "install_config")
    await db.commit()
    await db.refresh(token)
    return serialize_agent_token(token)


@router.put("/{agent_id}/status")
async def update_agent_status(
    agent_id: str,
    payload: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = await db.get(AgentToken, agent_id)
    if not token or token.tenant_id != user.tenant_id or not token.active:
        raise HTTPException(status_code=404, detail="Agent not found")
    token.status = payload.status
    flag_modified(token, "install_config")
    await db.commit()
    await db.refresh(token)
    return serialize_agent_token(token)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = await db.get(AgentToken, agent_id)
    if not token or token.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    token.active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
