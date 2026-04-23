#!/usr/bin/env python3
"""Portable LAS gateway that receives and forwards real logs/metrics/traces."""
from __future__ import annotations

import asyncio
import configparser
import hashlib
import ipaddress
import json
import logging
import os
import platform
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import unquote, urlparse


CONFIG_PATH = Path(os.getenv("LAS_CONFIG") or "/etc/las/gateway.conf")
# Keep in sync with backend/app/api/v1/endpoints/agents.py COMPONENT_LATEST_VERSION["gateway"]
GATEWAY_VERSION = "4.1.4"
LOG = logging.getLogger("las-gateway")
STATE: dict[str, Any] = {
    "logs": [],
    "host_metrics": [],
    "traces": [],
    "metrics": [],
}
STATE_LOCK = threading.Lock()
RUNTIME: dict[str, Any] = {}


def primary_config_section(config: configparser.ConfigParser) -> str:
    if config.has_section("las"):
        return "las"
    return config.default_section


def get_platform_url(config: configparser.ConfigParser) -> str:
    section = primary_config_section(config)
    return (
        config.get(section, "platform_url", fallback="").strip()
        or config.get(section, "las_url", fallback="").strip()
    )


def get_gateway_token(config: configparser.ConfigParser) -> str:
    section = primary_config_section(config)
    return (
        config.get(section, "gateway_token", fallback="").strip()
        or config.get(section, "token", fallback="").strip()
    )


def load_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_PATH):
        raise SystemExit(f"Configuration file not found: {CONFIG_PATH}")
    return parser


def build_client_ssl_context(config: configparser.ConfigParser) -> ssl.SSLContext | None:
    if not config.getboolean("mtls", "enabled", fallback=False):
        return None
    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=config.get("mtls", "ca_file", fallback="").strip() or None,
    )
    context.load_cert_chain(
        certfile=config.get("mtls", "client_cert_file", fallback="").strip(),
        keyfile=config.get("mtls", "client_key_file", fallback="").strip(),
    )
    context.check_hostname = True
    return context


def build_server_ssl_context(config: configparser.ConfigParser) -> ssl.SSLContext | None:
    if not config.getboolean("mtls", "enabled", fallback=False):
        return None
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(
        certfile=config.get("mtls", "server_cert_file", fallback="").strip(),
        keyfile=config.get("mtls", "server_key_file", fallback="").strip(),
    )
    context.load_verify_locations(cafile=config.get("mtls", "ca_file", fallback="").strip())
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def post_json(url: str, token: str, payload: dict, ssl_context: ssl.SSLContext | None = None) -> dict:
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20, context=ssl_context) as response:
        body = response.read().decode("utf-8") or "{}"
        return json.loads(body)


def get_json(url: str, token: str, ssl_context: ssl.SSLContext | None = None) -> dict:
    req = request.Request(
        url=url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with request.urlopen(req, timeout=30, context=ssl_context) as response:
        body = response.read().decode("utf-8") or "{}"
        return json.loads(body)


def download_file(url: str, token: str, destination: Path, ssl_context: ssl.SSLContext | None = None) -> None:
    req = request.Request(url=url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with request.urlopen(req, timeout=120, context=ssl_context) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def running_payload_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(__file__).resolve()


def restart_self() -> None:
    if getattr(sys, "frozen", False):
        os.execv(str(running_payload_path()), [str(running_payload_path()), *sys.argv[1:]])
    os.execv(sys.executable, [sys.executable, *sys.argv])


def apply_windows_update(temp_path: Path, target_path: Path) -> None:
    script_path = target_path.with_suffix(".update.cmd")
    script_path.write_text(
        "\r\n".join(
            [
                "@echo off",
                "timeout /t 3 /nobreak >NUL",
                "net stop LASGateway >NUL 2>NUL",
                f'move /Y "{temp_path}" "{target_path}" >NUL',
                "net start LASGateway >NUL 2>NUL",
                f'del "{script_path}" >NUL 2>NUL',
            ]
        ),
        encoding="ascii",
    )
    subprocess.Popen(["cmd.exe", "/c", str(script_path)], close_fds=True)
    raise SystemExit(0)


def apply_linux_update(temp_path: Path, target_path: Path) -> None:
    backup_path = target_path.with_suffix(target_path.suffix + ".bak")
    if target_path.exists():
        shutil.copy2(target_path, backup_path)
        current_mode = stat.S_IMODE(target_path.stat().st_mode)
    else:
        current_mode = 0o755
    shutil.move(str(temp_path), str(target_path))
    target_path.chmod(current_mode | stat.S_IXUSR)
    LOG.info("gateway updated to %s; restarting process", GATEWAY_VERSION)
    restart_self()


def check_for_update(config: configparser.ConfigParser, token: str, ssl_context: ssl.SSLContext | None) -> None:
    if not config.getboolean("updates", "enabled", fallback=True):
        return
    base_url = config.get("mtls", "platform_url", fallback=get_platform_url(config)).rstrip("/")
    os_name = platform.system().lower() or "linux"
    payload = get_json(
        f"{base_url}/api/v1/agents/updates/check?kind=gateway&version={GATEWAY_VERSION}&os_name={os_name}",
        token,
        ssl_context,
    )
    if not payload.get("update_available"):
        return
    expected_hash = (payload.get("sha256") or "").upper()
    download_url = payload.get("download_url")
    if not expected_hash or not download_url:
        raise RuntimeError("update metadata missing sha256 or download_url")
    target_path = running_payload_path()
    temp_path = target_path.with_suffix(target_path.suffix + f".{payload.get('latest_version')}.download")
    download_file(download_url, token, temp_path, ssl_context)
    actual_hash = sha256_file(temp_path)
    if actual_hash != expected_hash:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"update sha256 mismatch: expected {expected_hash}, got {actual_hash}")
    LOG.info("gateway update downloaded: %s -> %s", GATEWAY_VERSION, payload.get("latest_version"))
    if os.name == "nt":
        apply_windows_update(temp_path, target_path)
    apply_linux_update(temp_path, target_path)


def enqueue_logs(logs: list[dict]) -> None:
    if not logs:
        return
    with STATE_LOCK:
        STATE["logs"].extend(logs)


def parse_syslog_message(message: str) -> tuple[str, str]:
    lowered = message.lower()
    if "critical" in lowered or "crit" in lowered:
        return "critical", message
    if "error" in lowered or "failed" in lowered or "failure" in lowered:
        return "error", message
    if "warning" in lowered or "warn" in lowered:
        return "warn", message
    if "debug" in lowered:
        return "debug", message
    return "info", message


def syslog_entry(message: str, source_ip: str) -> dict:
    level, text = parse_syslog_message(message.strip())
    return {
        "timestamp": time.time(),
        "level": level,
        "source": "syslog",
        "group": "syslog_remote",
        "hostname": source_ip,
        "ip": source_ip,
        "message": text[:4000],
        "raw": message[:8000],
        "service": "syslog",
        "fields": {"source_ip": source_ip, "protocol": "syslog"},
    }


def syslog_udp_server(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        LOG.info("syslog UDP listening on %s:%s", host, port)
        while True:
            data, addr = sock.recvfrom(65535)
            message = data.decode("utf-8", errors="replace")
            enqueue_logs([syslog_entry(message, addr[0])])


def handle_syslog_tcp_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    with conn:
        data = conn.recv(65535)
        if not data:
            return
        for line in data.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                enqueue_logs([syslog_entry(line, addr[0])])


def syslog_tcp_server(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(100)
        LOG.info("syslog TCP listening on %s:%s", host, port)
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_syslog_tcp_client, args=(conn, addr), daemon=True).start()


def start_syslog_listeners(config: configparser.ConfigParser) -> None:
    if not config.getboolean("features", "logs", fallback=True):
        return
    if not config.getboolean("syslog", "enabled", fallback=True):
        return
    section = primary_config_section(config)
    host = config.get("syslog", "listen_host", fallback=config.get(section, "listen_host", fallback="0.0.0.0"))
    ports = [
        ("udp", config.getint("syslog", "udp_port", fallback=514), syslog_udp_server),
        ("tcp", config.getint("syslog", "tcp_port", fallback=514), syslog_tcp_server),
    ]
    for proto, port, target in ports:
        if port <= 0:
            continue
        threading.Thread(
            target=syslog_listener_guard,
            args=(proto, target, host, port),
            daemon=True,
        ).start()


def syslog_listener_guard(proto: str, target, host: str, port: int) -> None:
    try:
        target(host, port)
    except Exception as exc:
        LOG.warning("failed to run syslog %s listener on %s:%s: %s", proto, host, port, exc)


def probe_port(ip: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def ber_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + ber_length(len(value)) + value


def ber_integer(value: int) -> bytes:
    if value == 0:
        return ber_tlv(0x02, b"\x00")
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return ber_tlv(0x02, raw)


def ber_octet_string(value: str) -> bytes:
    return ber_tlv(0x04, value.encode("utf-8"))


def ber_null() -> bytes:
    return b"\x05\x00"


def ber_oid(oid: str) -> bytes:
    parts = [int(item) for item in oid.strip(".").split(".")]
    encoded = [parts[0] * 40 + parts[1]]
    for part in parts[2:]:
        stack = [part & 0x7F]
        part >>= 7
        while part:
            stack.append(0x80 | (part & 0x7F))
            part >>= 7
        encoded.extend(reversed(stack))
    return ber_tlv(0x06, bytes(encoded))


def ber_sequence(*items: bytes, tag: int = 0x30) -> bytes:
    return ber_tlv(tag, b"".join(items))


def decode_ber_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    return int.from_bytes(data[offset: offset + count], "big"), offset + count


def decode_ber_value(tag: int, value: bytes) -> Any:
    if tag in {0x02, 0x41, 0x42, 0x43, 0x46, 0x47}:
        return str(int.from_bytes(value, "big", signed=False))
    if tag == 0x04:
        return value.decode("utf-8", errors="replace")
    if tag == 0x40 and len(value) == 4:
        return ".".join(str(part) for part in value)
    if tag == 0x05:
        return None
    return value.hex()


def snmp_get_oid(ip: str, community: str, oid: str, port: int = 161, timeout_s: float = 1.5) -> Any:
    request_id = int(time.time() * 1000) & 0x7FFFFFFF
    varbind = ber_sequence(ber_oid(oid), ber_null())
    pdu = ber_sequence(
        ber_integer(request_id),
        ber_integer(0),
        ber_integer(0),
        ber_sequence(varbind),
        tag=0xA0,
    )
    message = ber_sequence(ber_integer(1), ber_octet_string(community or "public"), pdu)
    encoded_oid = ber_oid(oid)
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
    length, content_offset = decode_ber_length(data, value_offset + 1)
    return decode_ber_value(tag, data[content_offset: content_offset + length])


def snmp_get_basic(ip: str, community: str, port: int = 161) -> dict[str, Any]:
    oids = {
        "sys_descr": "1.3.6.1.2.1.1.1.0",
        "sys_uptime": "1.3.6.1.2.1.1.3.0",
        "sys_name": "1.3.6.1.2.1.1.5.0",
        "if_number": "1.3.6.1.2.1.2.1.0",
    }
    result: dict[str, Any] = {}
    for key, oid in oids.items():
        try:
            value = snmp_get_oid(ip, community, oid, port=port)
            if value not in {None, ""}:
                result[key] = value
        except OSError:
            continue
    return result


def snmp_status_name(value: Any) -> str:
    return {"1": "up", "2": "down", "3": "testing"}.get(str(value), "unknown")


def snmp_int(value: Any) -> int:
    try:
        parts = str(value).split()
        return int(parts[0]) if parts else 0
    except (TypeError, ValueError):
        return 0


def snmp_get_interfaces(ip: str, community: str, port: int = 161, max_interfaces: int = 256) -> list[dict[str, Any]]:
    try:
        if_number = snmp_int(snmp_get_oid(ip, community, "1.3.6.1.2.1.2.1.0", port=port))
    except OSError:
        return []
    interfaces: list[dict[str, Any]] = []
    for index in range(1, min(if_number, max_interfaces) + 1):
        def get(suffix: str) -> Any:
            try:
                return snmp_get_oid(ip, community, f"{suffix}.{index}", port=port, timeout_s=0.9)
            except OSError:
                return None

        name = get("1.3.6.1.2.1.31.1.1.1.1") or get("1.3.6.1.2.1.2.2.1.2")
        description = get("1.3.6.1.2.1.2.2.1.2")
        admin_status = get("1.3.6.1.2.1.2.2.1.7")
        oper_status = get("1.3.6.1.2.1.2.2.1.8")
        speed_mbps = snmp_int(get("1.3.6.1.2.1.31.1.1.1.15"))
        if not speed_mbps:
            speed_mbps = round(snmp_int(get("1.3.6.1.2.1.2.2.1.5")) / 1_000_000)
        interfaces.append(
            {
                "port_number": index,
                "name": str(name or f"if{index}"),
                "description": str(description or name or f"Interface {index}"),
                "speed_mbps": speed_mbps,
                "status": snmp_status_name(oper_status),
                "admin_status": snmp_status_name(admin_status),
                "rx_bytes": snmp_int(get("1.3.6.1.2.1.2.2.1.10")),
                "tx_bytes": snmp_int(get("1.3.6.1.2.1.2.2.1.16")),
                "rx_errors": snmp_int(get("1.3.6.1.2.1.2.2.1.14")),
                "tx_errors": snmp_int(get("1.3.6.1.2.1.2.2.1.20")),
                "media_type": "fiber" if str(name or "").lower().startswith(("gi", "te", "fo", "sfp")) else "copper",
            }
        )
    return interfaces


def reverse_dns(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def guess_asset_type(open_ports: list[int]) -> str:
    port_set = set(open_ports)
    if 161 in port_set and ({443, 8443} & port_set):
        return "firewall"
    if 161 in port_set and ({22, 23} & port_set):
        return "switch"
    if {3389, 445} & port_set:
        return "workstation"
    if {22, 80, 443, 3306, 5432, 6379, 8080, 8443} & port_set:
        return "server"
    if 161 in port_set:
        return "network"
    return "unknown"


def run_network_discovery_task(command: dict) -> dict:
    cidr = command.get("cidr")
    ports = [int(port) for port in command.get("ports", [])]
    timeout_s = max(0.05, int(command.get("timeout_ms", 350)) / 1000)
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(ip) for ip in network.hosts()]
    if len(hosts) > 512:
        raise RuntimeError("Discovery limitado a 512 enderecos por execucao.")
    assets: list[dict] = []
    scanned = 0
    for ip in hosts:
        scanned += 1
        open_ports = [port for port in ports if port != 161 and probe_port(ip, port, timeout_s)]
        snmp_data = snmp_get_basic(ip, command.get("snmp_community") or "public") if 161 in ports else {}
        interfaces = snmp_get_interfaces(ip, command.get("snmp_community") or "public") if snmp_data else []
        if snmp_data:
            open_ports.append(161)
        if not open_ports:
            continue
        hostname = reverse_dns(ip)
        snmp_enabled = 161 in open_ports
        syslog_enabled = 514 in open_ports or 6514 in open_ports
        sys_descr = snmp_data.get("sys_descr")
        assets.append(
            {
                "ip": ip,
                "hostname": snmp_data.get("sys_name") or hostname or ip,
                "asset_type": guess_asset_type(open_ports),
                "group": "net_w_snmp" if snmp_enabled else "net_discovered",
                "snmp_enabled": snmp_enabled,
                "snmp_community": command.get("snmp_community") if snmp_enabled else None,
                "syslog_enabled": syslog_enabled,
                "manufacturer": sys_descr.split()[0] if isinstance(sys_descr, str) and sys_descr else None,
                "model": sys_descr[:100] if isinstance(sys_descr, str) else None,
                "os_firmware": sys_descr[:100] if isinstance(sys_descr, str) else None,
                "port_count": int(snmp_data.get("if_number") or 0) if snmp_data.get("if_number") else None,
                "features": [f"udp:{port}" if port == 161 else f"tcp:{port}" for port in open_ports],
                "snmp": snmp_data,
                "ports": interfaces,
            }
        )
    return {
        "scanned": scanned,
        "discovered": len(assets),
        "net_w_snmp": sum(1 for asset in assets if asset["snmp_enabled"]),
        "assets": assets,
    }


def run_snmp_refresh_task(command: dict) -> dict:
    ip = command.get("ip")
    if not ip:
        raise RuntimeError("IP do ativo ausente.")
    port = int(command.get("snmp_port") or 161)
    snmp_data = snmp_get_basic(ip, command.get("snmp_community") or "public", port=port)
    interfaces = snmp_get_interfaces(ip, command.get("snmp_community") or "public", port=port) if snmp_data else []
    is_open = bool(snmp_data)
    sys_descr = snmp_data.get("sys_descr")
    return {
        "asset_id": command.get("asset_id"),
        "assets": [
            {
                "id": command.get("asset_id"),
                "ip": ip,
                "hostname": snmp_data.get("sys_name") or reverse_dns(ip) or ip,
                "asset_type": "network",
                "group": "net_w_snmp" if is_open else "net_discovered",
                "snmp_enabled": is_open,
                "snmp_community": command.get("snmp_community"),
                "manufacturer": sys_descr.split()[0] if isinstance(sys_descr, str) and sys_descr else None,
                "model": sys_descr[:100] if isinstance(sys_descr, str) else None,
                "os_firmware": sys_descr[:100] if isinstance(sys_descr, str) else None,
                "port_count": int(snmp_data.get("if_number") or 0) if snmp_data.get("if_number") else None,
                "features": [f"udp:{port}"] if is_open else [],
                "ports": interfaces,
            }
        ],
        "snmp": {"reachable": is_open, "port": port, **snmp_data},
        "ports": interfaces,
    }


def run_snmp_get_task(command: dict) -> dict:
    ip = command.get("ip")
    oid = command.get("oid")
    if not ip or not oid:
        raise RuntimeError("IP e OID sao obrigatorios para SNMP GET.")
    port = int(command.get("snmp_port") or command.get("port") or 161)
    community = command.get("snmp_community") or command.get("community") or "public"
    value = snmp_get_oid(ip, community, oid, port=port)
    return {
        "ip": ip,
        "oid": oid,
        "port": port,
        "community": community,
        "reachable": value not in {None, ""},
        "value": value,
    }


def _safe_metric_key(raw: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"_", ".", "-"} else "_" for ch in str(raw or ""))
    text = text.strip("._-")[:80]
    return text or "metric"


def _extract_custom_queries(cfg: dict) -> list[dict]:
    # Accept a few aliases to minimize friction in the UI JSON.
    raw = cfg.get("custom_queries")
    if raw is None:
        raw = cfg.get("queries")
    if raw is None:
        raw = cfg.get("customQueries")
    if not isinstance(raw, list):
        return []
    normalized: list[dict] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or item.get("sql") or "").strip()
        if not query:
            continue
        name = _safe_metric_key(item.get("name") or item.get("metric") or f"query_{len(normalized) + 1}")
        normalized.append({"name": name, "query": query})
    return normalized


def run_extension_collect_task(command: dict) -> dict:
    """Execute an extension instance inside the customer network (gateway-side)."""
    slug = str(command.get("extension_slug") or "").strip()
    instance_id = str(command.get("instance_id") or "").strip()
    cfg = command.get("config") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    if not slug:
        raise RuntimeError("extension_slug is required")

    if slug in {"postgresql", "postgres"}:
        return _collect_postgresql_extension("postgresql", instance_id, cfg)
    if slug in {"mysql", "mariadb"}:
        return _collect_mysql_extension("mysql", instance_id, cfg)
    if slug in {"redis"}:
        return _collect_redis_extension("redis", instance_id, cfg)

    raise RuntimeError(f"Extensao nao suportada no gateway ainda: {slug}")


def _collect_postgresql_extension(source: str, instance_id: str, cfg: dict) -> dict:
    import asyncio

    async def _run() -> dict:
        import asyncpg

        host = cfg.get("host") or "localhost"
        port = int(cfg.get("port") or 5432)
        user = cfg.get("user") or "postgres"
        password = cfg.get("password") or ""
        database = cfg.get("database") or "postgres"
        timeout_s = max(3, int(cfg.get("timeout_seconds") or 10))
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            timeout=timeout_s,
        )
        metrics: dict[str, float] = {}
        try:
            # Best-effort standard metrics (some environments may restrict these views).
            try:
                metrics["active_connections"] = float(
                    await conn.fetchval("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
            except Exception:
                pass
            try:
                cache_hit = await conn.fetchval(
                    """
                    SELECT sum(blks_hit) * 100.0 / nullif(sum(blks_hit + blks_read), 0)
                    FROM pg_stat_database
                    """
                )
                if cache_hit is not None:
                    metrics["cache_hit_ratio"] = float(round(float(cache_hit), 2))
            except Exception:
                pass

            for item in _extract_custom_queries(cfg):
                key = f"query.{item['name']}"
                try:
                    value = await conn.fetchval(item["query"])
                    if isinstance(value, bool):
                        metrics[key] = 1.0 if value else 0.0
                    elif isinstance(value, (int, float)):
                        metrics[key] = float(value)
                    elif value is not None:
                        metrics[key] = float(str(value).strip())
                except Exception:
                    continue
        finally:
            await conn.close()
        return metrics

    metrics = asyncio.run(_run())
    return {"extension_slug": source, "instance_id": instance_id, "metrics": metrics}


def _collect_mysql_extension(source: str, instance_id: str, cfg: dict) -> dict:
    import asyncio

    async def _run() -> dict:
        import aiomysql

        host = cfg.get("host") or "localhost"
        port = int(cfg.get("port") or 3306)
        user = cfg.get("user") or "root"
        password = cfg.get("password") or ""
        database = cfg.get("database") or "information_schema"
        timeout_s = max(3, int(cfg.get("timeout_seconds") or 10))
        conn = await aiomysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            db=database,
            connect_timeout=timeout_s,
        )
        metrics: dict[str, float] = {}
        try:
            try:
                async with conn.cursor() as cur:
                    await cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN ('Threads_connected','Uptime')")
                    rows = await cur.fetchall()
                status = {r[0]: r[1] for r in rows}
                if status.get("Threads_connected") is not None:
                    metrics["threads_connected"] = float(status["Threads_connected"])
                if status.get("Uptime") is not None:
                    metrics["uptime_s"] = float(status["Uptime"])
            except Exception:
                pass

            for item in _extract_custom_queries(cfg):
                key = f"query.{item['name']}"
                try:
                    async with conn.cursor() as cur:
                        await cur.execute(item["query"])
                        row = await cur.fetchone()
                    value = row[0] if row else None
                    if isinstance(value, bool):
                        metrics[key] = 1.0 if value else 0.0
                    elif isinstance(value, (int, float)):
                        metrics[key] = float(value)
                    elif value is not None:
                        metrics[key] = float(str(value).strip())
                except Exception:
                    continue
        finally:
            conn.close()
        return metrics

    metrics = asyncio.run(_run())
    return {"extension_slug": source, "instance_id": instance_id, "metrics": metrics}


def _collect_redis_extension(source: str, instance_id: str, cfg: dict) -> dict:
    import socket

    host = str(cfg.get("host") or "localhost")
    port = int(cfg.get("port") or 6379)
    password = str(cfg.get("password") or "")
    timeout_s = max(2, int(cfg.get("timeout_seconds") or 5))

    metrics: dict[str, float] = {}
    with socket.create_connection((host, port), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        if password:
            sock.sendall(f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n".encode("utf-8"))
            _ = sock.recv(4096)
        sock.sendall(b"*2\r\n$4\r\nINFO\r\n$11\r\nreplication\r\n")
        data = sock.recv(65535).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.startswith("connected_slaves:"):
                try:
                    metrics["connected_slaves"] = float(line.split(":", 1)[1].strip())
                except Exception:
                    pass
            if line.startswith("role:"):
                metrics["is_master"] = 1.0 if line.split(":", 1)[1].strip() == "master" else 0.0

    return {"extension_slug": source, "instance_id": instance_id, "metrics": metrics}


def run_gateway_task(task: dict) -> dict:
    task_type = task.get("type")
    command = task.get("command") or {}
    if task_type == "network_scan":
        return run_network_discovery_task(command)
    if task_type == "snmp_discovery":
        return run_snmp_refresh_task(command)
    if task_type == "snmp_get":
        return run_snmp_get_task(command)
    if task_type == "extension_collect":
        return run_extension_collect_task(command)
    raise RuntimeError(f"Tipo de task nao suportado pelo gateway: {task_type}")


def gateway_task_loop(config: configparser.ConfigParser) -> None:
    # Gateways can execute multiple task types (discovery/SNMP/extensions). Avoid coupling this loop
    # to a single flag (network_discovery), otherwise extensions never run.
    if not config.getboolean("features", "task_executor", fallback=True):
        return
    base_url = config.get("mtls", "platform_url", fallback=get_platform_url(config)).rstrip("/")
    token = get_gateway_token(config)
    ssl_context = build_client_ssl_context(config)
    poll_interval = max(config.getint("intervals", "task_poll_interval", fallback=20), 10)
    while True:
        time.sleep(poll_interval)
        try:
            payload = get_json(f"{base_url}/api/v1/agents/gateway/tasks/next", token, ssl_context)
            task = payload.get("task")
            if not task:
                continue
            LOG.info("gateway task received: %s %s", task.get("id"), task.get("type"))
            try:
                result = run_gateway_task(task)
                post_json(
                    f"{base_url}/api/v1/agents/gateway/tasks/{task['id']}/result",
                    token,
                    {"status": "completed", "result": result},
                    ssl_context=ssl_context,
                )
            except Exception as exc:
                LOG.exception("gateway task failed: %s", exc)
                post_json(
                    f"{base_url}/api/v1/agents/gateway/tasks/{task['id']}/result",
                    token,
                    {"status": "failed", "error": str(exc), "result": {}},
                    ssl_context=ssl_context,
                )
        except Exception as exc:
            LOG.debug("gateway task poll failed: %s", exc)


def update_loop(config: configparser.ConfigParser) -> None:
    token = get_gateway_token(config)
    ssl_context = build_client_ssl_context(config)
    interval = max(config.getint("updates", "check_interval", fallback=3600), 300)
    while True:
        time.sleep(interval)
        try:
            check_for_update(config, token, ssl_context)
        except SystemExit:
            raise
        except Exception as exc:
            LOG.warning("gateway auto-update check failed: %s", exc)


class GatewayHandler(BaseHTTPRequestHandler):
    def _send_bytes(self, status: int, content: bytes, *, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _safe_artifact_name(self, raw: str) -> str | None:
        name = (raw or "").strip()
        if not name:
            return None
        if "/" in name or "\\" in name or ".." in name:
            return None
        return name

    def _artifact_cache_dir(self) -> Path:
        config = RUNTIME.get("config")
        if config is None:
            return Path("/opt/las-gateway/cache")
        raw = config.get("artifacts", "cache_dir", fallback="").strip()
        if raw:
            return Path(raw)
        section = primary_config_section(config)
        install_dir = config.get(section, "install_dir", fallback="/opt/las-gateway").strip() or "/opt/las-gateway"
        return Path(install_dir) / "cache"

    def _guess_content_type(self, path: Path) -> str:
        if path.suffix.lower() in {".exe", ".bin"}:
            return "application/octet-stream"
        if path.suffix.lower() in {".json"}:
            return "application/json"
        if path.suffix.lower() in {".yml", ".yaml"}:
            return "application/x-yaml"
        return "text/plain; charset=utf-8"

    def _fetch_artifact(self, artifact_name: str) -> tuple[bytes, str]:
        cache_dir = self._artifact_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path = cache_dir / artifact_name
        if cached_path.exists() and cached_path.stat().st_size > 0:
            content = cached_path.read_bytes()
            return content, self._guess_content_type(cached_path)

        config = RUNTIME["config"]
        token = RUNTIME["token"]
        ssl_context = RUNTIME.get("client_ssl_context")
        base_url = config.get("mtls", "platform_url", fallback=get_platform_url(config)).rstrip("/")
        url = f"{base_url}/api/v1/agents/artifacts/{artifact_name}"
        tmp_path = cache_dir / f".{artifact_name}.{uuid.uuid4().hex}.tmp"
        download_file(url, token, tmp_path, ssl_context=ssl_context)
        tmp_path.replace(cached_path)
        content = cached_path.read_bytes()
        return content, self._guess_content_type(cached_path)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"status": "ok"})
            return

        if parsed.path.startswith("/api/v1/agents/artifacts/"):
            artifact_name = self._safe_artifact_name(unquote(parsed.path.split("/")[-1]))
            if not artifact_name:
                self._json(400, {"detail": "invalid artifact name"})
                return
            try:
                content, content_type = self._fetch_artifact(artifact_name)
            except Exception as exc:
                LOG.warning("artifact fetch failed for %s: %s", artifact_name, exc)
                self._json(503, {"detail": "artifact mirror unavailable"})
                return
            self._send_bytes(200, content, content_type=content_type, filename=artifact_name)
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"detail": "invalid json"})
            return

        if self.path == "/logs":
            enqueue_logs(payload.get("logs", []))
            self._json(202, {"queued": len(payload.get("logs", []))})
            return
        if self.path == "/host-metrics":
            entry = payload if "hostname" in payload else payload.get("entry")
            if entry:
                with STATE_LOCK:
                    STATE["host_metrics"].append(entry)
            self._json(202, {"queued": 1 if entry else 0})
            return
        if self.path == "/traces":
            with STATE_LOCK:
                STATE["traces"].append(payload)
            self._json(202, {"queued": 1})
            return
        if self.path == "/metrics":
            with STATE_LOCK:
                STATE["metrics"].append(payload)
            self._json(202, {"queued": 1})
            return
        if self.path == "/batch":
            with STATE_LOCK:
                STATE["logs"].extend(payload.get("logs", []))
                STATE["host_metrics"].extend(payload.get("host_metrics", []))
                if payload.get("traces"):
                    STATE["traces"].append(payload["traces"])
                if payload.get("metrics"):
                    STATE["metrics"].append(payload["metrics"])
            self._json(202, {"queued": True})
            return

        self._json(404, {"detail": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)


def merge_otel_payloads(payloads: list[dict], key: str) -> dict:
    merged: list[dict] = []
    for payload in payloads:
        merged.extend(payload.get(key, []))
    return {key: merged}


def flush_batches(config: configparser.ConfigParser) -> None:
    base_url = config.get("mtls", "platform_url", fallback=get_platform_url(config)).rstrip("/")
    token = get_gateway_token(config)
    batch_url = f"{base_url}/api/v1/ingest/gateway/batch"
    heartbeat_url = f"{base_url}/api/v1/ingest/gateway/heartbeat"
    section = primary_config_section(config)
    listen_port = config.getint(section, "listen_port", fallback=8080)

    ssl_context = build_client_ssl_context(config)

    while True:
        time.sleep(max(config.getint("intervals", "heartbeat_interval", fallback=60), 10))

        try:
            heartbeat = {
                "version": GATEWAY_VERSION,
                "host": socket.gethostname(),
                "port": listen_port,
                "public_endpoint": config.get(section, "public_endpoint", fallback=""),
                "metadata": {
                    "queued_logs": len(STATE["logs"]),
                    "queued_metrics": len(STATE["host_metrics"]),
                    "modules": {
                        "logs": config.getboolean("features", "logs", fallback=True),
                        "otel": config.getboolean("features", "otel", fallback=True),
                        "security": config.getboolean("features", "security", fallback=True),
                        "ids": config.getboolean("features", "ids", fallback=True),
                        "network_discovery": config.getboolean("features", "network_discovery", fallback=True),
                        "snmp": config.getboolean("features", "snmp", fallback=True),
                        "syslog": config.getboolean("syslog", "enabled", fallback=True),
                    },
                    "priority": config.getint("cluster", "priority", fallback=100),
                    "weight": config.getint("cluster", "weight", fallback=1),
                    "cluster_name": config.get("cluster", "cluster_name", fallback="default"),
                    "failover_only": config.getboolean("cluster", "failover_only", fallback=False),
                    "shared_with_tenants": config.getboolean("cluster", "shared_with_tenants", fallback=False),
                },
            }
            post_json(heartbeat_url, token, heartbeat, ssl_context=ssl_context)
        except Exception as exc:  # pragma: no cover
            LOG.exception("gateway heartbeat failed: %s", exc)

        with STATE_LOCK:
            has_data = any(STATE.values())
            batch = {
                "logs": STATE["logs"][:],
                "host_metrics": STATE["host_metrics"][:],
                "traces": merge_otel_payloads(STATE["traces"], "resourceSpans"),
                "metrics": merge_otel_payloads(STATE["metrics"], "resourceMetrics"),
            }

        if not has_data:
            continue

        try:
            response = post_json(batch_url, token, batch, ssl_context=ssl_context)
            LOG.info("gateway batch flushed: %s", response)
            with STATE_LOCK:
                STATE["logs"].clear()
                STATE["host_metrics"].clear()
                STATE["traces"].clear()
                STATE["metrics"].clear()
        except Exception as exc:  # pragma: no cover
            LOG.exception("gateway batch flush failed: %s", exc)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    config = load_config()
    section = primary_config_section(config)
    listen_host = config.get(section, "listen_host", fallback="0.0.0.0")
    listen_port = config.getint(section, "listen_port", fallback=8080)
    token = get_gateway_token(config)
    client_ssl_context = build_client_ssl_context(config)
    RUNTIME.clear()
    RUNTIME.update(
        {
            "config": config,
            "token": token,
            "client_ssl_context": client_ssl_context,
        }
    )
    try:
        check_for_update(config, token, client_ssl_context)
    except SystemExit:
        raise
    except Exception as exc:
        LOG.warning("initial gateway auto-update check failed: %s", exc)

    start_syslog_listeners(config)
    threading.Thread(target=flush_batches, args=(config,), daemon=True).start()
    threading.Thread(target=gateway_task_loop, args=(config,), daemon=True).start()
    threading.Thread(target=update_loop, args=(config,), daemon=True).start()
    server = ThreadingHTTPServer((listen_host, listen_port), GatewayHandler)
    server_ssl_context = build_server_ssl_context(config)
    if server_ssl_context:
        server.socket = server_ssl_context.wrap_socket(server.socket, server_side=True)
    LOG.info("gateway listening on %s:%s", listen_host, listen_port)
    server.serve_forever()
    return HTTPStatus.OK


if __name__ == "__main__":
    raise SystemExit(main())
