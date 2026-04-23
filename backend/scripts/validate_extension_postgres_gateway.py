#!/usr/bin/env python3
"""
End-to-end validation:
- Login as demo tenant admin
- Create a PostgreSQL extension instance
- Trigger "run now" (gateway execution)
- Poll tasks until completion

Designed to run *inside* the backend container where:
- API is available at http://127.0.0.1:8000
- The DB is reachable as configured by DATABASE_URL (usually via pgpool)

Usage (inside container):
  python /app/scripts/validate_extension_postgres_gateway.py
"""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse

import httpx


def _die(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def _db_conn_from_env() -> dict:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_ASYNC") or ""
    if url:
        parsed = urlparse(url)
        if parsed.hostname:
            return {
                "host": parsed.hostname,
                "port": int(parsed.port or 5432),
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
                "database": (parsed.path or "/postgres").lstrip("/") or "postgres",
            }

    # Fallback used by docker-compose stacks
    host = os.environ.get("POSTGRES_HOST") or ""
    if not host:
        _die("DATABASE_URL not found and POSTGRES_HOST not set")
    return {
        "host": host,
        "port": int(os.environ.get("POSTGRES_PORT") or 5432),
        "user": os.environ.get("POSTGRES_USER") or "postgres",
        "password": os.environ.get("POSTGRES_PASSWORD") or "",
        "database": os.environ.get("POSTGRES_DB") or "postgres",
    }


def main() -> int:
    base = "http://127.0.0.1:8000/api/v1"
    demo_user = os.environ.get("LAS_DEMO_USER") or "demo_las@soservices.com.br"
    demo_pass = os.environ.get("LAS_DEMO_PASS") or "admin"

    db_cfg = _db_conn_from_env()
    # In HA stacks, pgpool may temporarily refuse connections if backends flap.
    # Allow overriding to target a specific node for validation.
    host_override = os.environ.get("LAS_EXT_PG_HOST") or ""
    if host_override.strip():
        db_cfg["host"] = host_override.strip()

    with httpx.Client(base_url=base, timeout=20.0) as client:
        r = client.post("/auth/login", json={"username": demo_user, "password": demo_pass})
        if r.status_code >= 400:
            _die(f"Login failed: {r.status_code} {r.text[:300]}")

        instance_payload = {
            "name": "pgpool-demo",
            "enabled": True,
            "run_on": "gateway",
            "gateway_type": "integrations",
            "interval_seconds": 300,
            "config": {
                **db_cfg,
                "custom_queries": [
                    {"metric": "las.demo.ping", "query": "SELECT 1", "column": 0},
                ],
            },
        }

        created = client.post("/extensions/postgresql/instances", json=instance_payload)
        if created.status_code >= 400:
            _die(f"Create instance failed: {created.status_code} {created.text[:500]}")
        payload = created.json()
        instance_id = payload.get("instance_id") or payload.get("id")
        if not instance_id:
            _die(f"Create instance did not return instance_id: {created.text[:400]}")

        queued = client.post(f"/extensions/instances/{instance_id}/run")
        if queued.status_code >= 400:
            _die(f"Run instance failed: {queued.status_code} {queued.text[:500]}")
        task_id = queued.json().get("task_id")
        if not task_id:
            _die(f"Run instance did not return task_id: {queued.text[:400]}")

        # Poll management tasks list.
        deadline = time.time() + 120
        last_status = None
        while time.time() < deadline:
            tasks = client.get("/tasks", params={"limit": 200})
            tasks.raise_for_status()
            match = next((t for t in tasks.json() if t.get("id") == task_id), None)
            if match:
                last_status = match.get("status")
                if last_status in {"completed", "failed", "cancelled"}:
                    break
            time.sleep(2)

        if last_status != "completed":
            _die(f"Task did not complete in time. status={last_status!r} task_id={task_id}")

        # If we reached here, gateway executed and API persisted result.
        print("OK")
        print(f"instance_id={instance_id}")
        print(f"task_id={task_id}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
