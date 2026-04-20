#!/usr/bin/env python3
"""Portable LAS agent that sends real host telemetry directly or through gateways."""
from __future__ import annotations

import configparser
import hashlib
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
import time
import glob
from pathlib import Path
from typing import Any, Dict
from urllib import error, request

try:
    import psutil
except ImportError as exc:  # pragma: no cover - installation issue
    raise SystemExit("psutil is required for nexus_agent.py") from exc


CONFIG_PATH = Path(os.getenv("NEXUS_CONFIG", "/etc/las/agent.conf"))
AGENT_VERSION = "4.1.1"
LOG = logging.getLogger("las-agent")
LOG_OFFSETS: dict[str, int] = {}
DEFAULT_LOG_PATTERNS = [
    "/var/log/syslog",
    "/var/log/auth.log",
    "/var/log/messages",
    "/var/log/secure",
    "/var/log/nginx/*.log",
    "/var/log/apache2/*.log",
    "/var/log/httpd/*.log",
    "/var/log/mysql/*.log",
    "/var/log/postgresql/*.log",
    r"C:\LASAgent\logs\*.log",
    r"C:\inetpub\logs\LogFiles\*\*.log",
    r"C:\ProgramData\nginx\logs\*.log",
    r"C:\Apache24\logs\*.log",
]


def load_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_PATH):
        raise SystemExit(f"Configuration file not found: {CONFIG_PATH}")
    return parser


def build_ssl_context(config: configparser.ConfigParser, *, purpose: ssl.Purpose, check_hostname: bool = True) -> ssl.SSLContext | None:
    if not config.getboolean("mtls", "enabled", fallback=False):
        return None
    ca_file = config.get("mtls", "ca_file", fallback="").strip()
    cert_file = config.get("mtls", "client_cert_file", fallback="").strip()
    key_file = config.get("mtls", "client_key_file", fallback="").strip()
    if not ca_file or not cert_file or not key_file:
        raise RuntimeError("mTLS is enabled but certificate files are missing")
    context = ssl.create_default_context(purpose=purpose, cafile=ca_file)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    context.check_hostname = check_hostname
    return context


def post_json(url: str, token: str | None, payload: Dict[str, Any], ssl_context: ssl.SSLContext | None = None) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(
        url=url,
        data=data,
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=20, context=ssl_context) as response:
        body = response.read().decode("utf-8") or "{}"
        return json.loads(body)


def get_json(url: str, token: str | None, ssl_context: ssl.SSLContext | None = None) -> Dict[str, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url=url, headers=headers, method="GET")
    with request.urlopen(req, timeout=30, context=ssl_context) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def download_file(url: str, token: str | None, destination: Path, ssl_context: ssl.SSLContext | None = None) -> None:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url=url, headers=headers, method="GET")
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
                "net stop LASAgent >NUL 2>NUL",
                f'move /Y "{temp_path}" "{target_path}" >NUL',
                "net start LASAgent >NUL 2>NUL",
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
    LOG.info("agent updated to %s; restarting process", AGENT_VERSION)
    restart_self()


def check_for_update(config: configparser.ConfigParser, token: str, ssl_context: ssl.SSLContext | None) -> None:
    if not config.getboolean("updates", "enabled", fallback=True):
        return
    base_url = config.get("mtls", "platform_url", fallback=config["nexus"]["nexus_url"]).rstrip("/")
    os_name = platform.system().lower() or "linux"
    payload = get_json(
        f"{base_url}/api/v1/agents/updates/check?kind=agent&version={AGENT_VERSION}&os_name={os_name}",
        token,
        ssl_context,
    )
    if not payload.get("update_available"):
        return
    expected_hash = (payload.get("sha256") or "").upper()
    download_url = payload.get("download_url")
    if not expected_hash or not download_url:
        raise RuntimeError("update metadata missing sha256 or download_url")

    artifact_name = (payload.get("artifact") or "").strip()
    if not artifact_name:
        artifact_name = str(download_url).rstrip("/").split("/")[-1]

    target_path = running_payload_path()
    temp_path = target_path.with_suffix(target_path.suffix + f".{payload.get('latest_version')}.download")

    downloaded = False
    gateway_urls = get_gateway_urls(config)
    for gateway in gateway_urls:
        try:
            mirror_url = f"{gateway.rstrip('/')}/api/v1/agents/artifacts/{artifact_name}"
            LOG.info("trying update download via gateway mirror: %s", mirror_url)
            download_file(mirror_url, None, temp_path, ssl_context)
            downloaded = True
            break
        except Exception as exc:
            LOG.warning("gateway mirror download failed (%s): %s", gateway, exc)

    if not downloaded:
        download_file(download_url, token, temp_path, ssl_context)
    actual_hash = sha256_file(temp_path)
    if actual_hash != expected_hash:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"update sha256 mismatch: expected {expected_hash}, got {actual_hash}")
    LOG.info("agent update downloaded: %s -> %s", AGENT_VERSION, payload.get("latest_version"))
    if os.name == "nt":
        apply_windows_update(temp_path, target_path)
    apply_linux_update(temp_path, target_path)


def collect_metrics() -> Dict[str, Any]:
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    vm = psutil.virtual_memory()

    load1 = load5 = load15 = 0.0
    if hasattr(os, "getloadavg"):
        load1, load5, load15 = os.getloadavg()

    return {
        "cpuUsage": round(psutil.cpu_percent(interval=1), 2),
        "memoryUsage": round(vm.percent, 2),
        "diskUsage": round(disk.percent, 2),
        "loadAvg1": round(load1, 2),
        "loadAvg5": round(load5, 2),
        "loadAvg15": round(load15, 2),
        "netRxBytes": int(net.bytes_recv),
        "netTxBytes": int(net.bytes_sent),
        "diskReadBytes": int(psutil.disk_io_counters().read_bytes if psutil.disk_io_counters() else 0),
        "diskWriteBytes": int(psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0),
        "processesTotal": len(psutil.pids()),
        "processesRunning": sum(1 for proc in psutil.process_iter(attrs=["status"]) if proc.info["status"] == "running"),
    }


def collect_processes(limit: int = 15) -> list[Dict[str, Any]]:
    processes: list[Dict[str, Any]] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "username", "status", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name") or "unknown",
                    "username": info.get("username"),
                    "status": info.get("status"),
                    "cpuUsage": round(float(info.get("cpu_percent") or 0), 2),
                    "memoryUsage": round(float(info.get("memory_percent") or 0), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(processes, key=lambda item: (item["cpuUsage"], item["memoryUsage"]), reverse=True)[:limit]


def get_log_paths(config: configparser.ConfigParser) -> list[str]:
    raw = config.get("log_paths", "paths", fallback="").strip()
    patterns = [item.strip() for item in raw.split(",") if item.strip()] if raw else DEFAULT_LOG_PATTERNS
    paths: list[str] = []
    for item in patterns:
        matches = glob.glob(item)
        paths.extend(matches)
    return paths[:20]


def discover_log_paths() -> list[str]:
    paths: list[str] = []
    for pattern in DEFAULT_LOG_PATTERNS:
        paths.extend(glob.glob(pattern))
    return sorted(set(paths))[:50]


def collect_logs(config: configparser.ConfigParser, hostname: str, ip: str | None, max_lines: int = 25) -> list[Dict[str, Any]]:
    if not config.getboolean("features", "log_collection", fallback=False):
        return []
    entries: list[Dict[str, Any]] = []
    now = time.time()
    for path in get_log_paths(config):
        if len(entries) >= max_lines:
            break
        try:
            stat = os.stat(path)
            offset = LOG_OFFSETS.get(path, max(0, stat.st_size - 64_000))
            if stat.st_size < offset:
                offset = 0
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                lines = handle.readlines()
                LOG_OFFSETS[path] = handle.tell()
            for line in lines[-max_lines:]:
                message = line.strip()
                if not message:
                    continue
                level = "error" if "error" in message.lower() else "warn" if "warn" in message.lower() else "info"
                entries.append(
                    {
                        "timestamp": now,
                        "level": level,
                        "source": Path(path).name,
                        "group": "host_logs",
                        "hostname": hostname,
                        "ip": ip,
                        "message": message[:4000],
                        "raw": message,
                        "service": Path(path).stem,
                        "fields": {"path": path},
                    }
                )
                if len(entries) >= max_lines:
                    break
        except (FileNotFoundError, PermissionError, OSError) as exc:
            LOG.debug("log path unavailable %s: %s", path, exc)
    return entries


def detect_primary_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def collect_payload() -> Dict[str, Any]:
    uname = platform.uname()
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "ip": detect_primary_ip(),
        "os": uname.system.lower(),
        "os_version": uname.version,
        "kernel": uname.release,
        "arch": uname.machine,
        "manufacturer": None,
        "model": None,
        "agent_version": AGENT_VERSION,
        "uptime": int(time.time() - psutil.boot_time()),
        "cpu_cores": psutil.cpu_count() or 1,
        "memory_total_mb": int(vm.total / 1024 / 1024),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
        "metrics": collect_metrics(),
        "processes": collect_processes(),
        "detected_log_paths": discover_log_paths(),
    }


def get_gateway_urls(config: configparser.ConfigParser) -> list[str]:
    raw = config.get("routing", "gateway_urls", fallback="").strip()
    if not raw:
        return []
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def fetch_gateway_routes(base_url: str, token: str, ssl_context: ssl.SSLContext | None) -> list[dict]:
    req = request.Request(
        f"{base_url}/api/v1/agents/routing",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with request.urlopen(req, timeout=20, context=ssl_context) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    return payload.get("routes", [])


def order_gateway_routes(routes: list[dict], hostname: str) -> list[str]:
    if not routes:
        return []

    primary_pool: list[str] = []
    failover_pool: list[str] = []
    for route in routes:
        bucket = failover_pool if route.get("failover_only") else primary_pool
        bucket.extend([route["url"].rstrip("/")] * max(1, int(route.get("weight", 1))))

    weighted_pool = primary_pool or failover_pool
    if not weighted_pool:
        return []

    seed = int(hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:8], 16)
    start = seed % len(weighted_pool)
    ordered_urls = weighted_pool[start:] + weighted_pool[:start]
    ordered_urls.extend(url for url in failover_pool if url not in ordered_urls)

    unique_urls: list[str] = []
    for url in ordered_urls:
        if url not in unique_urls:
            unique_urls.append(url)
    return unique_urls


def send_via_gateway(gateway_urls: list[str], payload: Dict[str, Any], logs: list[Dict[str, Any]], ssl_context: ssl.SSLContext | None) -> bool:
    batch = {"host_metrics": [payload], "logs": logs, "traces": {"resourceSpans": []}, "metrics": {"resourceMetrics": []}}
    for gateway in gateway_urls:
        try:
            post_json(f"{gateway}/batch", None, batch, ssl_context=ssl_context)
            LOG.info("payload forwarded through gateway %s", gateway)
            return True
        except Exception as exc:
            LOG.warning("gateway %s unavailable: %s", gateway, exc)
    return False


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config = load_config()

    base_url = config["nexus"]["nexus_url"].rstrip("/")
    token = config["nexus"].get("agent_token")
    heartbeat_interval = config.getint("intervals", "heartbeat_interval", fallback=60)
    update_interval = config.getint("updates", "check_interval", fallback=3600)
    heartbeat_url = f"{base_url}/api/v1/ingest/agent/heartbeat"
    routing_refresh_interval = config.getint("routing", "routing_refresh_interval", fallback=300)
    hostname = socket.gethostname()
    gateway_urls = get_gateway_urls(config)
    last_route_refresh = 0.0
    api_ssl_context = build_ssl_context(config, purpose=ssl.Purpose.SERVER_AUTH, check_hostname=True)
    gateway_ssl_context = build_ssl_context(config, purpose=ssl.Purpose.SERVER_AUTH, check_hostname=True)
    last_update_check = 0.0

    while True:
        try:
            now = time.time()
            if token and now - last_update_check >= max(update_interval, 300):
                try:
                    check_for_update(config, token, api_ssl_context)
                except SystemExit:
                    raise
                except Exception as exc:
                    LOG.warning("auto-update check failed: %s", exc)
                last_update_check = now
            if token and (now - last_route_refresh >= max(routing_refresh_interval, 60)):
                try:
                    routing_base_url = config.get("mtls", "platform_url", fallback=base_url).rstrip("/")
                    gateway_urls = order_gateway_routes(fetch_gateway_routes(routing_base_url, token, api_ssl_context), hostname) or gateway_urls
                    last_route_refresh = now
                    LOG.info("gateway routing refreshed: %s", gateway_urls)
                except Exception as exc:
                    LOG.warning("failed to refresh gateway routing: %s", exc)

            payload = collect_payload()
            logs = collect_logs(config, payload["hostname"], payload.get("ip"))
            if gateway_urls:
                if not send_via_gateway(gateway_urls, payload, logs, gateway_ssl_context):
                    heartbeat_target = f"{config.get('mtls', 'platform_url', fallback=base_url).rstrip('/')}/api/v1/ingest/agent/heartbeat"
                    response = post_json(heartbeat_target, token, payload, ssl_context=api_ssl_context)
                    LOG.info("heartbeat sent directly after gateway failover: %s", response)
                    if logs:
                        log_url = f"{config.get('mtls', 'platform_url', fallback=base_url).rstrip('/')}/api/v1/ingest/logs"
                        post_json(log_url, token, {"logs": logs}, ssl_context=api_ssl_context)
                    last_route_refresh = 0.0
            else:
                heartbeat_target = f"{config.get('mtls', 'platform_url', fallback=base_url).rstrip('/')}/api/v1/ingest/agent/heartbeat"
                response = post_json(heartbeat_target, token, payload, ssl_context=api_ssl_context)
                LOG.info("heartbeat sent: %s", response)
                if logs:
                    log_url = f"{config.get('mtls', 'platform_url', fallback=base_url).rstrip('/')}/api/v1/ingest/logs"
                    post_json(log_url, token, {"logs": logs}, ssl_context=api_ssl_context)
        except error.HTTPError as exc:
            LOG.error("heartbeat failed with HTTP %s", exc.code)
        except Exception as exc:  # pragma: no cover - network/runtime
            LOG.exception("heartbeat failed: %s", exc)

        time.sleep(max(heartbeat_interval, 10))


if __name__ == "__main__":
    raise SystemExit(main())
