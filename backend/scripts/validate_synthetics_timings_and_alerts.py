#!/usr/bin/env python3
"""
End-to-end validation for Synthetic monitoring:
- Create a passing URL monitor and run it
- Verify timings/resources are populated in detail endpoint
- Create a failing URL monitor (threshold=1) and run it
- Verify an incident/alert is created

Run inside backend container:
  python /app/scripts/validate_synthetics_timings_and_alerts.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import httpx


def _die(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def _poll(fn, *, timeout_s: int = 90, interval_s: float = 2.0):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(interval_s)
    return last


def main() -> int:
    base = "http://127.0.0.1:8000/api/v1"
    demo_user = os.environ.get("LAS_DEMO_USER") or "demo_las@soservices.com.br"
    demo_pass = os.environ.get("LAS_DEMO_PASS") or "admin"

    ok_name = f"synthetic-ok-{uuid.uuid4().hex[:8]}"
    bad_name = f"synthetic-bad-{uuid.uuid4().hex[:8]}"

    with httpx.Client(base_url=base, timeout=25.0) as client:
        r = client.post("/auth/login", json={"username": demo_user, "password": demo_pass})
        if r.status_code >= 400:
            _die(f"Login failed: {r.status_code} {r.text[:300]}")

        # Passing check against internal frontend (HTTP, no TLS)
        ok_test = client.post(
            "/synthetics",
            json={
                "name": ok_name,
                "type": "url_monitor",
                "url": "http://las-frontend-ha/",
                "method": "GET",
                "interval_seconds": 60,
                "timeout_seconds": 20,
                "enabled": True,
                "alert_on_failure": True,
                "consecutive_failures_threshold": 1,
            },
        )
        ok_test.raise_for_status()
        ok_id = ok_test.json().get("id")
        if not ok_id:
            _die(f"Create synthetic OK did not return id: {ok_test.text[:200]}")

        ok_run = client.post(f"/synthetics/{ok_id}/run")
        ok_run.raise_for_status()

        def ok_detail_ready():
            d = client.get(f"/synthetics/{ok_id}/detail").json()
            results = d.get("results") or []
            if not results:
                return None
            latest = results[0]
            timings = latest.get("timings") or {}
            if not timings or timings.get("total_ms") is None:
                return None
            return d

        ok_detail = _poll(ok_detail_ready, timeout_s=120)
        if not ok_detail:
            _die("Synthetic OK did not produce timings in time")

        latest = (ok_detail.get("results") or [{}])[0]
        timings = latest.get("timings") or {}
        baseline = ok_detail.get("baseline") or {}
        timing_baseline = ok_detail.get("timing_baseline") or {}

        # Failing check (connection refused/timeout) to force an incident
        bad_test = client.post(
            "/synthetics",
            json={
                "name": bad_name,
                "type": "url_monitor",
                "url": "http://127.0.0.1:1/",
                "method": "GET",
                "interval_seconds": 60,
                "timeout_seconds": 5,
                "enabled": True,
                "alert_on_failure": True,
                "consecutive_failures_threshold": 1,
            },
        )
        bad_test.raise_for_status()
        bad_id = bad_test.json().get("id")
        if not bad_id:
            _die(f"Create synthetic BAD did not return id: {bad_test.text[:200]}")

        bad_run = client.post(f"/synthetics/{bad_id}/run")
        bad_run.raise_for_status()

        # Wait for an incident/alert to show up.
        def incident_ready():
            items = client.get("/incidents", params={"limit": 200, "q": bad_name, "timeframe": "24h"}).json()
            for it in items:
                if it.get("entity_type") == "synthetic" and bad_name in (it.get("name") or ""):
                    return it
            return None

        incident = _poll(incident_ready, timeout_s=120)
        if not incident:
            _die("Synthetic BAD did not create an incident in time")

        print("OK")
        print(f"ok_test_id={ok_id}")
        print(f"ok_timings_total_ms={timings.get('total_ms')}")
        print(f"ok_timing_dns_ms={timings.get('dns_ms')}")
        print(f"ok_baseline_p95={baseline.get('p95_response_ms')}")
        print(f"ok_timing_baseline_p95_total={timing_baseline.get('p95_total_ms')}")
        print(f"bad_test_id={bad_id}")
        print(f"incident_id={incident.get('id')}")
        print(f"incident_severity={incident.get('severity')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

