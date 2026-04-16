#!/usr/bin/env python3
"""Portable Nexus agent that sends real host telemetry to the API."""
from __future__ import annotations

import configparser
import json
import logging
import os
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict
from urllib import error, request

try:
    import psutil
except ImportError as exc:  # pragma: no cover - installation issue
    raise SystemExit("psutil is required for nexus_agent.py") from exc


CONFIG_PATH = Path(os.getenv("NEXUS_CONFIG", "/etc/nexus/nexus.conf"))
LOG = logging.getLogger("nexus-agent")


def load_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_PATH):
        raise SystemExit(f"Configuration file not found: {CONFIG_PATH}")
    return parser


def post_json(url: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8") or "{}"
        return json.loads(body)


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
        "agent_version": "4.0.0",
        "uptime": int(time.time() - psutil.boot_time()),
        "cpu_cores": psutil.cpu_count() or 1,
        "memory_total_mb": int(vm.total / 1024 / 1024),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
        "metrics": collect_metrics(),
    }


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config = load_config()

    base_url = config["nexus"]["nexus_url"].rstrip("/")
    token = config["nexus"]["agent_token"]
    heartbeat_interval = config.getint("intervals", "heartbeat_interval", fallback=60)
    heartbeat_url = f"{base_url}/api/v1/ingest/agent/heartbeat"

    while True:
        try:
            response = post_json(heartbeat_url, token, collect_payload())
            LOG.info("heartbeat sent: %s", response)
        except error.HTTPError as exc:
            LOG.error("heartbeat failed with HTTP %s", exc.code)
        except Exception as exc:  # pragma: no cover - network/runtime
            LOG.exception("heartbeat failed: %s", exc)

        time.sleep(max(heartbeat_interval, 10))


if __name__ == "__main__":
    raise SystemExit(main())
