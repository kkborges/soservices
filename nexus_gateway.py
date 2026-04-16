#!/usr/bin/env python3
"""Portable LAS gateway that receives and forwards real logs/metrics/traces."""
from __future__ import annotations

import configparser
import json
import logging
import os
import socket
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request


CONFIG_PATH = Path(os.getenv("NEXUS_CONFIG", "/etc/nexus/gateway.conf"))
LOG = logging.getLogger("las-gateway")
STATE: dict[str, Any] = {
    "logs": [],
    "host_metrics": [],
    "traces": [],
    "metrics": [],
}


def load_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_PATH):
        raise SystemExit(f"Configuration file not found: {CONFIG_PATH}")
    return parser


def post_json(url: str, token: str, payload: dict) -> dict:
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8") or "{}"
        return json.loads(body)


class GatewayHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
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
            STATE["logs"].extend(payload.get("logs", []))
            self._json(202, {"queued": len(payload.get("logs", []))})
            return
        if self.path == "/host-metrics":
            entry = payload if "hostname" in payload else payload.get("entry")
            if entry:
                STATE["host_metrics"].append(entry)
            self._json(202, {"queued": 1 if entry else 0})
            return
        if self.path == "/traces":
            STATE["traces"].append(payload)
            self._json(202, {"queued": 1})
            return
        if self.path == "/metrics":
            STATE["metrics"].append(payload)
            self._json(202, {"queued": 1})
            return
        if self.path == "/batch":
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
    base_url = config["nexus"]["nexus_url"].rstrip("/")
    token = config["nexus"]["gateway_token"]
    batch_url = f"{base_url}/api/v1/ingest/gateway/batch"
    heartbeat_url = f"{base_url}/api/v1/ingest/gateway/heartbeat"
    listen_port = config.getint("nexus", "listen_port", fallback=8080)

    while True:
        time.sleep(max(config.getint("intervals", "heartbeat_interval", fallback=60), 10))

        try:
            heartbeat = {
                "version": "4.0.0",
                "host": socket.gethostname(),
                "port": listen_port,
                "metadata": {"queued_logs": len(STATE["logs"]), "queued_metrics": len(STATE["host_metrics"])},
            }
            post_json(heartbeat_url, token, heartbeat)
        except Exception as exc:  # pragma: no cover
            LOG.exception("gateway heartbeat failed: %s", exc)

        if not any(STATE.values()):
            continue

        batch = {
            "logs": STATE["logs"][:],
            "host_metrics": STATE["host_metrics"][:],
            "traces": merge_otel_payloads(STATE["traces"], "resourceSpans"),
            "metrics": merge_otel_payloads(STATE["metrics"], "resourceMetrics"),
        }

        try:
            response = post_json(batch_url, token, batch)
            LOG.info("gateway batch flushed: %s", response)
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
    listen_host = config["nexus"].get("listen_host", "0.0.0.0")
    listen_port = config.getint("nexus", "listen_port", fallback=8080)

    threading.Thread(target=flush_batches, args=(config,), daemon=True).start()
    server = ThreadingHTTPServer((listen_host, listen_port), GatewayHandler)
    LOG.info("gateway listening on %s:%s", listen_host, listen_port)
    server.serve_forever()
    return HTTPStatus.OK


if __name__ == "__main__":
    raise SystemExit(main())
