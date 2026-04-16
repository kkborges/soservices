"""In-process runtime tasks for discovery and SNMP polling."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models import Host, NetworkAsset, NetworkPort, Task

_RUNNING_TASKS: dict[str, asyncio.Task] = {}
_CANCELLED_TASKS: set[str] = set()
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


def launch_runtime_task(task_id: str, coro: Any) -> None:
    task = asyncio.create_task(coro)
    _RUNNING_TASKS[task_id] = task

    def _cleanup(_: asyncio.Task) -> None:
        _RUNNING_TASKS.pop(task_id, None)
        _CANCELLED_TASKS.discard(task_id)

    task.add_done_callback(_cleanup)


def cancel_runtime_task(task_id: str) -> bool:
    task = _RUNNING_TASKS.get(task_id)
    _CANCELLED_TASKS.add(task_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


async def _update_task(task_id: str, **updates: Any) -> None:
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        for field, value in updates.items():
            setattr(task, field, value)
        await db.commit()


def _guess_asset_type(open_ports: list[int], sys_descr: str | None = None, hostname: str | None = None) -> str:
    port_set = set(open_ports)
    description = f"{sys_descr or ''} {hostname or ''}".lower()
    if any(keyword in description for keyword in HOST_DESCRIPTION_KEYWORDS):
        if {3389, 445}.intersection(port_set) or "windows" in description or "microsoft" in description:
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
    if {3389, 445}.intersection(port_set):
        return "workstation"
    if {22, 80, 443, 3306, 5432, 6379, 8080, 8443}.intersection(port_set):
        return "server"
    if 161 in port_set and 23 in port_set:
        return "switch"
    if 161 in port_set:
        return "network"
    return "unknown"


async def _probe_port(ip: str, port: int, timeout_s: float) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout_s)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _ber_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _ber_length(len(value)) + value


def _ber_integer(value: int) -> bytes:
    if value == 0:
        return _ber_tlv(0x02, b"\x00")
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return _ber_tlv(0x02, raw)


def _ber_oid(oid: str) -> bytes:
    parts = [int(item) for item in oid.strip(".").split(".")]
    encoded = [parts[0] * 40 + parts[1]]
    for part in parts[2:]:
        stack = [part & 0x7F]
        part >>= 7
        while part:
            stack.append(0x80 | (part & 0x7F))
            part >>= 7
        encoded.extend(reversed(stack))
    return _ber_tlv(0x06, bytes(encoded))


def _ber_sequence(*items: bytes, tag: int = 0x30) -> bytes:
    return _ber_tlv(tag, b"".join(items))


def _decode_ber_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    return int.from_bytes(data[offset: offset + count], "big"), offset + count


def _decode_ber_value(tag: int, value: bytes) -> Any:
    if tag in {0x02, 0x41, 0x42, 0x43, 0x46, 0x47}:
        return str(int.from_bytes(value, "big", signed=False))
    if tag == 0x04:
        return value.decode("utf-8", errors="replace")
    if tag == 0x40 and len(value) == 4:
        return ".".join(str(part) for part in value)
    if tag == 0x05:
        return None
    return value.hex()


def _snmp_get_oid_sync(ip: str, community: str, oid: str, port: int = 161, timeout_s: float = 1.5) -> Any:
    request_id = int(time.time() * 1000) & 0x7FFFFFFF
    encoded_oid = _ber_oid(oid)
    varbind = _ber_sequence(encoded_oid, b"\x05\x00")
    pdu = _ber_sequence(
        _ber_integer(request_id),
        _ber_integer(0),
        _ber_integer(0),
        _ber_sequence(varbind),
        tag=0xA0,
    )
    message = _ber_sequence(_ber_integer(1), _ber_tlv(0x04, (community or "public").encode("utf-8")), pdu)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout_s)
        sock.sendto(message, (ip, port))
        data, _ = sock.recvfrom(65535)
    oid_index = data.find(encoded_oid)
    if oid_index < 0:
        return True
    value_offset = oid_index + len(encoded_oid)
    if value_offset >= len(data):
        return True
    tag = data[value_offset]
    length, content_offset = _decode_ber_length(data, value_offset + 1)
    return _decode_ber_value(tag, data[content_offset: content_offset + length])


def _snmp_get_basic_sync(ip: str, community: str, port: int = 161) -> dict[str, Any]:
    oids = {
        "sys_name": "1.3.6.1.2.1.1.5.0",
        "sys_descr": "1.3.6.1.2.1.1.1.0",
        "sys_uptime": "1.3.6.1.2.1.1.3.0",
        "if_number": "1.3.6.1.2.1.2.1.0",
    }
    result: dict[str, Any] = {}
    for key, oid in oids.items():
        try:
            value = _snmp_get_oid_sync(ip, community, oid, port=port)
            if value not in {None, ""}:
                result[key] = value
        except OSError:
            continue
    return result


async def _scan_ports(ip: str, ports: list[int], timeout_s: float, snmp_community: str = "public") -> list[int]:
    tcp_ports = [port for port in ports if port != 161]
    checks = await asyncio.gather(*[_probe_port(ip, port, timeout_s) for port in tcp_ports], return_exceptions=False)
    open_ports = [port for port, is_open in zip(tcp_ports, checks) if is_open]
    if 161 in ports and await asyncio.to_thread(_snmp_get_basic_sync, ip, snmp_community):
        open_ports.append(161)
    return open_ports


async def _reverse_dns(ip: str) -> str | None:
    try:
        return (await asyncio.to_thread(socket.gethostbyaddr, ip))[0]
    except Exception:
        return None


async def _snmp_get_basic(ip: str, community: str, port: int = 161) -> dict[str, Any]:
    try:
        from pysnmp.hlapi.asyncio import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            getCmd,
        )
    except Exception:
        return await asyncio.to_thread(_snmp_get_basic_sync, ip, community, port)

    engine = SnmpEngine()
    target = await UdpTransportTarget.create((ip, port), timeout=3, retries=0)
    oids = {
        "sys_name": "1.3.6.1.2.1.1.5.0",
        "sys_descr": "1.3.6.1.2.1.1.1.0",
        "sys_uptime": "1.3.6.1.2.1.1.3.0",
        "if_number": "1.3.6.1.2.1.2.1.0",
    }
    result: dict[str, Any] = {}
    for key, oid in oids.items():
        try:
            error_indication, error_status, _, var_binds = await getCmd(
                engine,
                CommunityData(community),
                target,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
            if error_indication or error_status:
                continue
            for var_bind in var_binds:
                result[key] = str(var_bind[1])
        except Exception:
            continue
    if result:
        return result
    return await asyncio.to_thread(_snmp_get_basic_sync, ip, community, port)


def _snmp_status_name(value: Any) -> str:
    return {"1": "up", "2": "down", "3": "testing"}.get(str(value), "unknown")


def _snmp_int(value: Any) -> int:
    try:
        parts = str(value).split()
        return int(parts[0]) if parts else 0
    except (TypeError, ValueError):
        return 0


def _snmp_get_interfaces_sync(ip: str, community: str, port: int = 161, max_interfaces: int = 256) -> list[dict[str, Any]]:
    try:
        if_number = _snmp_int(_snmp_get_oid_sync(ip, community, "1.3.6.1.2.1.2.1.0", port=port))
    except OSError:
        return []
    interfaces: list[dict[str, Any]] = []
    for index in range(1, min(if_number, max_interfaces) + 1):
        def get(suffix: str) -> Any:
            try:
                return _snmp_get_oid_sync(ip, community, f"{suffix}.{index}", port=port, timeout_s=0.9)
            except OSError:
                return None

        name = get("1.3.6.1.2.1.31.1.1.1.1") or get("1.3.6.1.2.1.2.2.1.2")
        description = get("1.3.6.1.2.1.2.2.1.2")
        admin_status = get("1.3.6.1.2.1.2.2.1.7")
        oper_status = get("1.3.6.1.2.1.2.2.1.8")
        speed_mbps = _snmp_int(get("1.3.6.1.2.1.31.1.1.1.15"))
        if not speed_mbps:
            speed_mbps = round(_snmp_int(get("1.3.6.1.2.1.2.2.1.5")) / 1_000_000)
        interfaces.append(
            {
                "port_number": index,
                "name": str(name or f"if{index}"),
                "description": str(description or name or f"Interface {index}"),
                "speed_mbps": speed_mbps,
                "status": _snmp_status_name(oper_status),
                "admin_status": _snmp_status_name(admin_status),
                "rx_bytes": _snmp_int(get("1.3.6.1.2.1.2.2.1.10")),
                "tx_bytes": _snmp_int(get("1.3.6.1.2.1.2.2.1.16")),
                "rx_errors": _snmp_int(get("1.3.6.1.2.1.2.2.1.14")),
                "tx_errors": _snmp_int(get("1.3.6.1.2.1.2.2.1.20")),
                "media_type": "fiber" if str(name or "").lower().startswith(("gi", "te", "fo", "sfp")) else "copper",
            }
        )
    return interfaces


async def _snmp_get_interfaces(ip: str, community: str, port: int = 161) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_snmp_get_interfaces_sync, ip, community, port)


async def snmp_get_value(ip: str, community: str, oid: str, port: int = 161) -> Any:
    return await asyncio.to_thread(_snmp_get_oid_sync, ip, community, oid, port)


async def _upsert_network_ports(db: Any, asset: NetworkAsset, ports: list[dict[str, Any]]) -> None:
    if not ports:
        return
    now = datetime.now(timezone.utc)
    existing_result = await db.execute(select(NetworkPort).where(NetworkPort.asset_id == asset.id))
    existing = {port.port_number: port for port in existing_result.scalars().all()}
    ports_up = 0
    ports_down = 0
    for item in ports:
        number = int(item.get("port_number") or 0)
        if number <= 0:
            continue
        port = existing.get(number)
        if not port:
            port = NetworkPort(
                id=str(uuid.uuid4()),
                tenant_id=asset.tenant_id,
                asset_id=asset.id,
                port_number=number,
            )
            db.add(port)
        port.name = item.get("name") or port.name
        port.description = item.get("description") or port.description
        port.media_type = item.get("media_type") or port.media_type
        port.speed_mbps = int(item.get("speed_mbps") or 0)
        port.status = item.get("status") or port.status
        port.rx_bytes = int(item.get("rx_bytes") or 0)
        port.tx_bytes = int(item.get("tx_bytes") or 0)
        port.rx_errors = int(item.get("rx_errors") or 0)
        port.tx_errors = int(item.get("tx_errors") or 0)
        port.last_updated = now
        if port.status == "up":
            ports_up += 1
        elif port.status == "down":
            ports_down += 1
    asset.ports_up = ports_up
    asset.ports_down = ports_down
    asset.ports_copper = sum(1 for item in ports if item.get("media_type") == "copper")
    asset.ports_fiber = sum(1 for item in ports if item.get("media_type") == "fiber")


async def _upsert_discovered_entities(
    tenant_id: str,
    ip: str,
    open_ports: list[int],
    snmp_community: str,
) -> None:
    now = datetime.now(timezone.utc)
    hostname = await _reverse_dns(ip)
    snmp_data = await _snmp_get_basic(ip, snmp_community) if 161 in open_ports else {}
    interfaces = await _snmp_get_interfaces(ip, snmp_community) if snmp_data else []
    snmp_enabled = bool(snmp_data)
    resolved_name = snmp_data.get("sys_name") or hostname or ip
    syslog_enabled = 514 in open_ports or 6514 in open_ports
    sys_descr = snmp_data.get("sys_descr")
    manufacturer = sys_descr.split()[0] if sys_descr else None
    asset_group = "net_w_snmp" if snmp_enabled else "net_discovered"
    asset_type = _guess_asset_type(open_ports, sys_descr, resolved_name)
    is_network_asset = asset_type in NETWORK_ASSET_TYPES

    async with AsyncSessionLocal() as db:
        if not is_network_asset:
            host_result = await db.execute(select(Host).where(Host.tenant_id == tenant_id, Host.ip == ip))
            host = host_result.scalar_one_or_none()
            if not host:
                host = Host(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    ip=ip,
                    hostname=hostname or ip,
                    os=sys_descr[:100] if sys_descr else None,
                    monitoring_mode="discovered",
                )
                db.add(host)

            host.hostname = resolved_name or host.hostname or ip
            host.status = "online"
            host.last_seen = now
            host.otel_enabled = host.otel_enabled or False

        if not is_network_asset:
            await db.commit()
            return

        asset_result = await db.execute(select(NetworkAsset).where(NetworkAsset.tenant_id == tenant_id, NetworkAsset.ip == ip))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            asset = NetworkAsset(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                ip=ip,
            )
            db.add(asset)

        asset.hostname = resolved_name or asset.hostname or ip
        asset.asset_type = asset_type
        asset.group = asset_group
        asset.status = "online"
        asset.last_scan = now
        asset.snmp_enabled = snmp_enabled
        asset.snmp_community = snmp_community if snmp_enabled else asset.snmp_community
        asset.syslog_enabled = syslog_enabled
        asset.os_firmware = sys_descr[:100] if sys_descr else asset.os_firmware
        asset.manufacturer = manufacturer or asset.manufacturer
        asset.uptime = int(snmp_data.get("sys_uptime", "0").split()[0]) if snmp_data.get("sys_uptime") else asset.uptime
        asset.port_count = int(snmp_data.get("if_number", asset.port_count or 0) or 0)
        existing_features = set(asset.features or [])
        if 161 in open_ports:
            existing_features.discard("tcp:161")
        asset.features = sorted({*existing_features, *[f"udp:{port}" if port == 161 else f"tcp:{port}" for port in open_ports]})
        await _upsert_network_ports(db, asset, interfaces)

        await db.commit()


async def run_network_discovery(
    task_id: str,
    tenant_id: str,
    cidr: str,
    ports: list[int],
    snmp_community: str = "public",
    timeout_ms: int = 350,
) -> None:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        await _update_task(task_id, status="failed", error=str(exc), completed_at=datetime.now(timezone.utc))
        return

    hosts = [str(ip) for ip in network.hosts()]
    if len(hosts) > 512:
        await _update_task(
            task_id,
            status="failed",
            error="Discovery limitado a 512 endereços por execução.",
            completed_at=datetime.now(timezone.utc),
        )
        return

    await _update_task(task_id, status="running", started_at=datetime.now(timezone.utc), progress=1)

    discovered = 0
    snmp_assets = 0
    scanned = 0
    semaphore = asyncio.Semaphore(64)

    async def _scan_ip(ip: str) -> tuple[str, list[int]]:
        async with semaphore:
            return ip, await _scan_ports(ip, ports, timeout_ms / 1000, snmp_community)

    for result in asyncio.as_completed([_scan_ip(ip) for ip in hosts]):
        if task_id in _CANCELLED_TASKS:
            await _update_task(
                task_id,
                status="cancelled",
                completed_at=datetime.now(timezone.utc),
                progress=100,
            )
            return

        ip, open_ports = await result
        scanned += 1
        if open_ports:
            discovered += 1
            if 161 in open_ports:
                snmp_assets += 1
            await _upsert_discovered_entities(tenant_id, ip, open_ports, snmp_community)

        if scanned % 8 == 0 or scanned == len(hosts):
            await _update_task(
                task_id,
                progress=round((scanned / max(len(hosts), 1)) * 100, 2),
                result={
                    "cidr": cidr,
                    "scanned": scanned,
                    "discovered": discovered,
                    "net_w_snmp": snmp_assets,
                    "ports": ports,
                },
            )

    await _update_task(
        task_id,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        progress=100,
        result={
            "cidr": cidr,
            "scanned": scanned,
            "discovered": discovered,
            "net_w_snmp": snmp_assets,
            "ports": ports,
        },
    )


async def run_snmp_refresh(task_id: str, tenant_id: str, asset_id: str) -> None:
    await _update_task(task_id, status="running", started_at=datetime.now(timezone.utc), progress=5)
    async with AsyncSessionLocal() as db:
        asset = await db.get(NetworkAsset, asset_id)
        if not asset or asset.tenant_id != tenant_id:
            await _update_task(task_id, status="failed", error="Ativo não encontrado", completed_at=datetime.now(timezone.utc))
            return
        community = asset.snmp_community or "public"
        data = await _snmp_get_basic(asset.ip, community, asset.snmp_port or 161)
        interfaces = await _snmp_get_interfaces(asset.ip, community, asset.snmp_port or 161) if data else []
        if data:
            sys_descr = data.get("sys_descr")
            asset.hostname = data.get("sys_name") or asset.hostname
            asset.os_firmware = sys_descr[:100] if sys_descr else asset.os_firmware
            asset.manufacturer = sys_descr.split()[0] if sys_descr else asset.manufacturer
            asset.port_count = int(data.get("if_number", asset.port_count or 0) or 0)
            asset.last_poll = datetime.now(timezone.utc)
            asset.status = "online"
            await _upsert_network_ports(db, asset, interfaces)
            await db.commit()
            await _update_task(
                task_id,
                status="completed",
                completed_at=datetime.now(timezone.utc),
                progress=100,
                result={"asset_id": asset_id, "snmp": data},
            )
            return

    await _update_task(
        task_id,
        status="failed",
        completed_at=datetime.now(timezone.utc),
        error="Sem resposta SNMP do ativo.",
    )


async def run_snmp_get(
    task_id: str,
    tenant_id: str,
    ip: str,
    community: str,
    oid: str,
    port: int = 161,
) -> None:
    await _update_task(task_id, status="running", started_at=datetime.now(timezone.utc), progress=10)
    try:
        value = await snmp_get_value(ip, community or "public", oid, port)
    except Exception as exc:
        await _update_task(
            task_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            progress=100,
            error=f"SNMP GET sem resposta: {exc}",
            result={"tenant_id": tenant_id, "ip": ip, "oid": oid, "port": port, "reachable": False},
        )
        return

    await _update_task(
        task_id,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        progress=100,
        result={
            "tenant_id": tenant_id,
            "ip": ip,
            "oid": oid,
            "port": port,
            "community": community or "public",
            "reachable": value not in {None, ""},
            "value": value,
        },
    )
