"""Gateway routing and failover helpers for tenants and shared clusters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import ipaddress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Gateway, Tenant


DEFAULT_STALE_AFTER = timedelta(minutes=3)
DEFAULT_OFFLINE_AFTER = timedelta(minutes=10)


def _config_value(config: dict | None, key: str, default):
    if not isinstance(config, dict):
        return default
    return config.get(key, default)


def _bool_value(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_value(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def gateway_public_url(gateway: Gateway) -> str | None:
    config = gateway.config or {}
    custom = str(config.get("public_endpoint") or "").strip().rstrip("/")
    if custom:
        return custom
    host = str(gateway.host or "").strip()
    if not host or host == "0.0.0.0":
        return None
    port = gateway.port or 8080
    scheme = "https" if gateway.tls_enabled or port == 9443 else "http"
    return f"{scheme}://{host}:{port}"


def _is_agent_routable_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        if not host:
            return False
        ipaddress.ip_address(host)
        return True
    except ValueError:
        lowered = host.lower()
        if lowered.endswith((".lan", ".local", ".internal", ".home")):
            return False
        return "." in lowered


def gateway_health(gateway: Gateway) -> tuple[str, bool]:
    now = datetime.now(timezone.utc)
    config = gateway.config or {}
    heartbeat_interval = max(30, _int_value(_config_value(config, "heartbeat_interval", 60), 60))
    stale_after = timedelta(seconds=max(heartbeat_interval * 2, int(DEFAULT_STALE_AFTER.total_seconds())))
    offline_after = timedelta(seconds=max(heartbeat_interval * 5, int(DEFAULT_OFFLINE_AFTER.total_seconds())))

    if gateway.last_heartbeat and (now - gateway.last_heartbeat) <= stale_after:
        return ("online", True)
    if gateway.last_heartbeat and (now - gateway.last_heartbeat) <= offline_after:
        return ("stale", False)
    if not gateway.last_heartbeat and gateway.status in {"pending_install", "provisioning"}:
        return ("pending_install", False)
    if gateway.status in {"online", "active"}:
        return ("stale", False)
    return (gateway.status or "offline", False)


def gateway_route_record(gateway: Gateway, *, shared: bool) -> dict | None:
    config = gateway.config or {}
    url = str(config.get("agent_route_url") or "").strip().rstrip("/") or gateway_public_url(gateway)
    if not url:
        return None
    if not config.get("allow_private_dns_routes") and not _is_agent_routable_url(url):
        return None
    status, healthy = gateway_health(gateway)
    priority = max(1, _int_value(_config_value(config, "priority", 100), 100))
    weight = max(1, _int_value(_config_value(config, "weight", 1), 1))
    return {
        "id": gateway.id,
        "name": gateway.name,
        "type": gateway.type,
        "url": url,
        "priority": priority,
        "weight": weight,
        "cluster_name": str(_config_value(config, "cluster_name", "default")),
        "failover_only": _bool_value(_config_value(config, "failover_only", False)),
        "shared_with_tenants": _bool_value(_config_value(config, "shared_with_tenants", False)),
        "healthy": healthy,
        "status": status,
        "tls_enabled": bool(gateway.tls_enabled),
        "compress_enabled": bool(gateway.compress_enabled),
        "encrypt_enabled": bool(gateway.encrypt_enabled),
        "tenant_scope": "shared" if shared else "tenant",
        "last_heartbeat": gateway.last_heartbeat.isoformat() if gateway.last_heartbeat else None,
    }


async def resolve_gateway_routes(db: AsyncSession, tenant_id: str) -> list[dict]:
    tenant_result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    tenants = tenant_result.scalars().all()
    internal_tenant_ids = {
        tenant.id
        for tenant in tenants
        if isinstance(tenant.settings, dict) and tenant.settings.get("internal_platform")
    }

    gateway_result = await db.execute(select(Gateway))
    routes: list[dict] = []
    fallback_routes: list[dict] = []
    for gateway in gateway_result.scalars().all():
        shared_gateway = gateway.tenant_id in internal_tenant_ids and gateway.tenant_id != tenant_id
        same_tenant = gateway.tenant_id == tenant_id
        if not same_tenant and not shared_gateway:
            continue

        route = gateway_route_record(gateway, shared=shared_gateway)
        if not route:
            continue

        if shared_gateway and not route["shared_with_tenants"]:
            continue

        if route["healthy"]:
            routes.append(route)
        else:
            fallback_routes.append(route)

    fallback_candidates = [route for route in fallback_routes if route["tenant_scope"] != "shared"]
    ordered = sorted(
        routes or fallback_candidates,
        key=lambda item: (
            item["failover_only"],
            item["priority"],
            item["tenant_scope"] == "shared",
            item["cluster_name"],
            item["name"].lower(),
        ),
    )
    return ordered
