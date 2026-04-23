"""
Synthetic Test Worker — Executes URL, API, app flow, SSL and DNS checks.
"""
import asyncio
import logging
import ssl
import socket
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import httpx
import re
from urllib.parse import urlparse, urljoin
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


RESOURCE_URL_RE = re.compile(
    r"""(?is)(?:src|href)\s*=\s*["']([^"']+)["']"""
)


def _extract_resource_urls(html: str, base_url: str, limit: int = 30) -> list[str]:
    if not html or not base_url:
        return []
    urls: list[str] = []
    for match in RESOURCE_URL_RE.findall(html):
        raw = (match or "").strip()
        if not raw or raw.startswith(("data:", "javascript:", "#")):
            continue
        absolute = urljoin(base_url, raw)
        if absolute.startswith(("http://", "https://")):
            urls.append(absolute)
        if len(urls) >= limit:
            break
    # de-dup while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in urls:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


async def _preflight_dns_connect_tls(url: str, timeout_s: int) -> tuple[dict[str, Any], str | None]:
    """Best-effort network timings. This is not the same socket used by httpx."""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return {}, None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    timings: dict[str, Any] = {}

    import time

    loop = asyncio.get_running_loop()
    dns_start = time.monotonic()
    try:
        addrs = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception:
        return {}, None
    dns_ms = (time.monotonic() - dns_start) * 1000
    timings["dns_ms"] = round(dns_ms, 2)
    ip = addrs[0][4][0] if addrs and addrs[0] and addrs[0][4] else None
    if not ip:
        return timings, None

    connect_start = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(1, int(timeout_s)))
    try:
        sock.connect((ip, port))
        timings["connect_ms"] = round((time.monotonic() - connect_start) * 1000, 2)
        if parsed.scheme == "https":
            tls_start = time.monotonic()
            ctx = ssl.create_default_context()
            tls_sock = ctx.wrap_socket(sock, server_hostname=host)
            tls_sock.do_handshake()
            timings["tls_ms"] = round((time.monotonic() - tls_start) * 1000, 2)
            tls_sock.close()
        else:
            sock.close()
    except Exception:
        try:
            sock.close()
        except Exception:
            pass
        return timings, ip
    return timings, ip


async def _fetch_with_ttfb(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    headers: dict,
    body: bytes | None,
    timeout_s: int,
) -> tuple[httpx.Response, dict[str, Any], bytes, int]:
    """Fetch URL streaming to measure TTFB + total bytes (best-effort)."""
    import time

    timings: dict[str, Any] = {}
    total_bytes = 0
    body_prefix = bytearray()
    start = time.monotonic()
    async with client.stream(method=method, url=url, headers=headers, content=body, timeout=timeout_s) as resp:
        async for chunk in resp.aiter_bytes():
            if "ttfb_ms" not in timings:
                timings["ttfb_ms"] = round((time.monotonic() - start) * 1000, 2)
            total_bytes += len(chunk or b"")
            if chunk and len(body_prefix) < 50_000:
                remaining = 50_000 - len(body_prefix)
                body_prefix.extend(chunk[:remaining])
        total_ms = (time.monotonic() - start) * 1000
        timings["total_ms"] = round(total_ms, 2)
        ttfb_ms = float(timings.get("ttfb_ms") or total_ms)
        timings["download_ms"] = round(max(0.0, total_ms - ttfb_ms), 2)
        return resp, timings, bytes(body_prefix), total_bytes


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.synthetic_worker.dispatch_due_tests")
def dispatch_due_tests():
    """Find all synthetic tests that are due to run and dispatch them."""
    return run_async(_dispatch_due_tests_async())


async def _dispatch_due_tests_async():
    from app.db.base import AsyncSessionLocal
    from app.models import SyntheticTest
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    dispatched = 0

    async with AsyncSessionLocal() as db:
        tests_result = await db.execute(
            select(SyntheticTest).where(SyntheticTest.enabled == True)
        )
        tests = tests_result.scalars().all()

        for test in tests:
            # Check if test is due
            if test.last_check:
                next_run = test.last_check + timedelta(seconds=test.interval_seconds)
                if now < next_run:
                    continue

            # Dispatch appropriate worker
            if test.type.value == "ssl_check":
                run_ssl_check.apply_async(args=[test.id])
            elif test.type.value == "app_flow":
                run_app_flow.apply_async(args=[test.id])
            elif test.type.value == "api_monitor":
                run_api_monitor.apply_async(args=[test.id])
            else:
                run_url_monitor.apply_async(args=[test.id])

            dispatched += 1

    return {"dispatched": dispatched}


@celery_app.task(name="app.workers.synthetic_worker.run_url_monitor",
                 queue="synthetic")
def run_url_monitor(test_id: str):
    return run_async(_run_http_check(test_id, "url_monitor"))


@celery_app.task(name="app.workers.synthetic_worker.run_api_monitor",
                 queue="synthetic")
def run_api_monitor(test_id: str):
    return run_async(_run_http_check(test_id, "api_monitor"))


async def _run_http_check(test_id: str, check_type: str):
    from app.db.base import AsyncSessionLocal
    from app.models import SyntheticTest, SyntheticResult
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        test_result = await db.execute(select(SyntheticTest).where(SyntheticTest.id == test_id))
        test = test_result.scalar_one_or_none()
        if not test:
            return

        now = datetime.now(timezone.utc)
        result = SyntheticResult(
            id=str(uuid.uuid4()),
            test_id=test.id,
            tenant_id=test.tenant_id,
            timestamp=now,
            location="primary",
        )

        try:
            preflight_timings, remote_ip = await _preflight_dns_connect_tls(test.url or "", test.timeout_seconds or 30)
            async with httpx.AsyncClient(
                timeout=test.timeout_seconds,
                follow_redirects=True,
                verify=True,
            ) as client:
                # Build request
                headers = test.headers or {}
                if test.auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {test.auth_value}"
                elif test.auth_type == "api_key":
                    headers["X-API-Key"] = test.auth_value

                resp, timing, snippet_bytes, total_bytes = await _fetch_with_ttfb(
                    client,
                    method=test.method or "GET",
                    url=test.url,
                    headers=headers,
                    body=test.body.encode() if test.body else None,
                    timeout_s=int(test.timeout_seconds or 30),
                )
                elapsed_ms = float(timing.get("total_ms") or 0)

                result.status_code = resp.status_code
                result.response_time_ms = elapsed_ms
                result.response_headers = dict(resp.headers)
                body_text = snippet_bytes.decode("utf-8", errors="replace")
                result.response_body_snippet = body_text[:500]
                result.timings = {**(preflight_timings or {}), **(timing or {}), "bytes": total_bytes}
                result.remote_ip = remote_ip

                # Run assertions for api_monitor
                assertions_passed = 0
                assertions_failed = 0
                assertion_details = []

                for assertion in (test.assertions or []):
                    a_type = assertion.get("type")
                    a_op = assertion.get("operator", "eq")
                    a_val = assertion.get("value")
                    passed = False
                    actual = None
                    error = None

                    try:
                        if a_type == "status_code":
                            actual = resp.status_code
                            passed = _compare(actual, a_op, int(a_val))
                        elif a_type == "response_time":
                            actual = elapsed_ms
                            passed = _compare(actual, a_op, float(a_val))
                        elif a_type == "body_contains":
                            actual = a_val
                            passed = a_val in resp.text
                        elif a_type == "header":
                            header_name = assertion.get("name", "")
                            actual = resp.headers.get(header_name, "")
                            passed = _compare(actual, a_op, a_val)
                        elif a_type == "json_path":
                            import json
                            from jsonpath_ng import parse as jp_parse
                            body = resp.json()
                            path = assertion.get("path", "$")
                            matches = jp_parse(path).find(body)
                            actual = [m.value for m in matches]
                            passed = len(matches) > 0 if a_op == "exists" else _compare(actual[0] if actual else None, a_op, a_val)
                    except Exception as e:
                        error = str(e)
                        passed = False

                    if passed:
                        assertions_passed += 1
                    else:
                        assertions_failed += 1

                    assertion_details.append({
                        "type": a_type, "operator": a_op, "expected": a_val,
                        "actual": str(actual), "passed": passed, "error": error
                    })

                result.assertions_passed = assertions_passed
                result.assertions_failed = assertions_failed
                result.assertion_details = assertion_details

                # Determine status
                if resp.status_code >= 500:
                    result.status = "down"
                elif assertions_failed > 0:
                    result.status = "degraded" if assertions_passed > 0 else "down"
                else:
                    result.status = "up" if resp.status_code < 400 else "degraded"

                # Resource waterfall for HTML pages (URL monitor only; best-effort)
                result.resources = []
                content_type = (resp.headers.get("content-type") or "").lower()
                if check_type == "url_monitor" and "text/html" in content_type and body_text:
                    resources = _extract_resource_urls(body_text, test.url or "")
                    resource_items = []
                    for resource_url in resources[:20]:
                        try:
                            r_resp, r_timing, _, r_bytes = await _fetch_with_ttfb(
                                client,
                                method="GET",
                                url=resource_url,
                                headers={},
                                body=None,
                                timeout_s=min(10, max(3, int(test.timeout_seconds or 30))),
                            )
                            resource_items.append(
                                {
                                    "url": resource_url,
                                    "status_code": r_resp.status_code,
                                    "total_ms": r_timing.get("total_ms"),
                                    "ttfb_ms": r_timing.get("ttfb_ms"),
                                    "bytes": r_bytes,
                                }
                            )
                        except Exception:
                            continue
                    result.resources = resource_items

        except httpx.TimeoutException:
            result.status = "down"
            result.error_message = "Timeout"
        except ssl.SSLCertVerificationError as e:
            result.status = "down"
            result.error_message = f"SSL verification failed: {e}"
        except Exception as e:
            result.status = "down"
            result.error_message = str(e)

        db.add(result)

        # Update test stats
        test.last_check = now
        test.last_status = result.status
        test.last_response_ms = result.response_time_ms

        await db.commit()

        # Update rolling stats (avg response + uptime based on recent history).
        try:
            from sqlalchemy import desc
            rows = await db.execute(
                select(SyntheticResult.status, SyntheticResult.response_time_ms)
                .where(SyntheticResult.tenant_id == test.tenant_id, SyntheticResult.test_id == test.id)
                .order_by(desc(SyntheticResult.timestamp))
                .limit(100)
            )
            recent = rows.all()
            if recent:
                up_like = [r for r in recent if r[0] in {"up", "degraded"}]
                test.uptime_pct = round((len(up_like) / max(len(recent), 1)) * 100, 2)
                times = [float(r[1]) for r in up_like if r[1] is not None]
                test.avg_response_ms = round(sum(times) / max(len(times), 1), 2) if times else None
                await db.commit()
        except Exception:
            pass

        # Create alert if failed
        if result.status == "down":
            _check_synthetic_alert.apply_async(args=[test.id])

        return {"test_id": test_id, "status": result.status, "response_ms": result.response_time_ms}


@celery_app.task(name="app.workers.synthetic_worker.run_ssl_check", queue="synthetic")
def run_ssl_check(test_id: str):
    return run_async(_run_ssl_check(test_id))


async def _run_ssl_check(test_id: str):
    from app.db.base import AsyncSessionLocal
    from app.models import SyntheticTest, SyntheticResult
    from sqlalchemy import select
    import ssl, socket
    from urllib.parse import urlparse

    async with AsyncSessionLocal() as db:
        test_result = await db.execute(select(SyntheticTest).where(SyntheticTest.id == test_id))
        test = test_result.scalar_one_or_none()
        if not test:
            return

        now = datetime.now(timezone.utc)
        result = SyntheticResult(
            id=str(uuid.uuid4()),
            test_id=test.id,
            tenant_id=test.tenant_id,
            timestamp=now,
        )

        try:
            parsed = urlparse(test.url)
            hostname = parsed.hostname
            port = parsed.port or 443

            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

            # Parse certificate
            not_after = datetime.strptime(
                cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
            ).replace(tzinfo=timezone.utc)

            not_before = datetime.strptime(
                cert["notBefore"], "%b %d %H:%M:%S %Y %Z"
            ).replace(tzinfo=timezone.utc)

            days_remaining = (not_after - now).days
            issuer = dict(x[0] for x in cert.get("issuer", []))
            subject = dict(x[0] for x in cert.get("subject", []))

            result.ssl_valid = True
            result.ssl_expires_at = not_after
            result.ssl_days_remaining = days_remaining
            result.ssl_issuer = issuer.get("organizationName", issuer.get("commonName", ""))
            result.ssl_subject = subject.get("commonName", "")

            warn_days = test.ssl_warn_days or 30
            crit_days = test.ssl_crit_days or 7

            if days_remaining <= 0:
                result.status = "down"
                result.error_message = "Certificate expired"
            elif days_remaining <= crit_days:
                result.status = "degraded"
                result.error_message = f"Certificate expires in {days_remaining} days (critical)"
            elif days_remaining <= warn_days:
                result.status = "degraded"
                result.error_message = f"Certificate expires in {days_remaining} days (warning)"
            else:
                result.status = "up"

        except ssl.SSLCertVerificationError as e:
            result.ssl_valid = False
            result.status = "down"
            result.error_message = f"SSL verification failed: {e}"
        except Exception as e:
            result.status = "down"
            result.error_message = str(e)

        db.add(result)
        test.last_check = now
        test.last_status = result.status
        await db.commit()

        return {
            "test_id": test_id,
            "status": result.status,
            "days_remaining": result.ssl_days_remaining,
            "expires_at": result.ssl_expires_at.isoformat() if result.ssl_expires_at else None,
        }


@celery_app.task(name="app.workers.synthetic_worker.run_app_flow", queue="synthetic")
def run_app_flow(test_id: str):
    """Execute Playwright-based app flow test."""
    return run_async(_run_app_flow(test_id))


async def _run_app_flow(test_id: str):
    from app.db.base import AsyncSessionLocal
    from app.models import SyntheticTest, SyntheticResult
    from sqlalchemy import select
    import time

    async with AsyncSessionLocal() as db:
        test_result = await db.execute(select(SyntheticTest).where(SyntheticTest.id == test_id))
        test = test_result.scalar_one_or_none()
        if not test:
            return

        now = datetime.now(timezone.utc)
        result = SyntheticResult(
            id=str(uuid.uuid4()),
            test_id=test.id,
            tenant_id=test.tenant_id,
            timestamp=now,
        )

        try:
            from playwright.async_api import async_playwright

            steps = test.flow_steps or []
            step_details = []
            steps_passed = 0

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                start = time.monotonic()

                for i, step in enumerate(steps):
                    step_result = {"step": i + 1, "action": step.get("action"), "passed": False}
                    try:
                        action = step.get("action")
                        if action == "navigate":
                            await page.goto(step["url"], timeout=test.timeout_seconds * 1000)
                        elif action == "click":
                            await page.click(step["selector"], timeout=5000)
                        elif action == "fill":
                            await page.fill(step["selector"], step["value"])
                        elif action == "wait":
                            await page.wait_for_selector(step["selector"], timeout=5000)
                        elif action == "assert_text":
                            text = await page.text_content(step["selector"])
                            assert step["value"] in (text or "")
                        elif action == "assert_url":
                            assert step["value"] in page.url
                        elif action == "screenshot":
                            pass  # could upload to S3

                        step_result["passed"] = True
                        steps_passed += 1
                    except Exception as e:
                        step_result["error"] = str(e)
                    step_details.append(step_result)

                elapsed_ms = (time.monotonic() - start) * 1000
                await browser.close()

            result.steps_total = len(steps)
            result.steps_passed = steps_passed
            result.step_details = step_details
            result.response_time_ms = elapsed_ms
            result.status = "up" if steps_passed == len(steps) else ("degraded" if steps_passed > 0 else "down")

        except Exception as e:
            result.status = "down"
            result.error_message = str(e)

        db.add(result)
        test.last_check = now
        test.last_status = result.status
        await db.commit()
        return {"test_id": test_id, "status": result.status}


@celery_app.task(name="app.workers.synthetic_worker.check_synthetic_alert")
def _check_synthetic_alert(test_id: str):
    """Create alert if synthetic test is consistently failing."""
    return run_async(_check_synthetic_alert_async(test_id))


async def _check_synthetic_alert_async(test_id: str) -> dict:
    from app.db.base import AsyncSessionLocal
    from app.models import Alert, SyntheticResult, SyntheticTest
    from sqlalchemy import select, desc

    async with AsyncSessionLocal() as db:
        test = await db.get(SyntheticTest, test_id)
        if not test:
            return {"status": "missing"}

        # Look at recent executions to decide if we should open/close an incident.
        threshold = max(1, int(test.consecutive_failures_threshold or 2))
        rows = await db.execute(
            select(SyntheticResult)
            .where(SyntheticResult.test_id == test.id, SyntheticResult.tenant_id == test.tenant_id)
            .order_by(desc(SyntheticResult.timestamp))
            .limit(max(10, threshold + 3))
        )
        recent = rows.scalars().all()

        consecutive_down = 0
        for item in recent:
            if item.status == "down":
                consecutive_down += 1
            else:
                break

        active_alert_rows = await db.execute(
            select(Alert)
            .where(
                Alert.tenant_id == test.tenant_id,
                Alert.entity_type == "synthetic",
                Alert.entity_id == test.id,
                Alert.metric == "synthetic.availability",
                Alert.status != "resolved",
            )
            .order_by(desc(Alert.triggered_at))
            .limit(1)
        )
        active_alert = active_alert_rows.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if consecutive_down >= threshold and test.alert_on_failure:
            if active_alert:
                active_alert.trigger_count = int(active_alert.trigger_count or 1) + 1
                active_alert.description = f"Teste sintetico em falha. Falhas consecutivas: {consecutive_down}/{threshold}."
                active_alert.triggered_at = now
            else:
                alert = Alert(
                    id=str(uuid.uuid4()),
                    tenant_id=test.tenant_id,
                    name=f"Synthetic DOWN: {test.name}",
                    description=f"Teste sintetico em falha. Falhas consecutivas: {consecutive_down}/{threshold}.",
                    severity="high" if consecutive_down >= max(3, threshold) else "medium",
                    entity_type="synthetic",
                    entity_id=test.id,
                    entity_name=test.name,
                    metric="synthetic.availability",
                    observed_value=0,
                    threshold_value=1,
                    condition_op="lt",
                    status="active",
                    triggered_at=now,
                )
                db.add(alert)
            await db.commit()
            return {"status": "alert_open", "consecutive_down": consecutive_down}

        # Resolve existing alert when recovered.
        if active_alert and (test.last_status in {"up", "degraded"}):
            active_alert.status = "resolved"
            active_alert.resolved_at = now
            await db.commit()
            return {"status": "alert_resolved"}

        return {"status": "no_action", "consecutive_down": consecutive_down}


def _compare(actual, op: str, expected) -> bool:
    try:
        if op == "eq": return actual == expected
        if op == "ne": return actual != expected
        if op == "gt": return float(actual) > float(expected)
        if op == "lt": return float(actual) < float(expected)
        if op == "gte": return float(actual) >= float(expected)
        if op == "lte": return float(actual) <= float(expected)
        if op == "contains": return str(expected) in str(actual)
        if op == "not_contains": return str(expected) not in str(actual)
        if op == "exists": return actual is not None
        return False
    except Exception:
        return False
