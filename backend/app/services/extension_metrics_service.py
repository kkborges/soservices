"""Helpers to store extension/plugin datapoints in OtelMetric.

Extensions are executed either:
- server-side (when targets are public/reachable), or
- gateway-side (preferred), inside the customer network.

The platform always persists metrics server-side so dashboards/alerts work uniformly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExtensionConfig, OtelMetric


async def store_extension_metrics(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str | None,
    source: str,
    metrics: dict[str, Any],
    *,
    status: str = "completed",
    error: str | None = None,
) -> int:
    """Persist numeric metrics and update the instance status."""
    now = datetime.now(timezone.utc)
    created = 0
    for key, value in (metrics or {}).items():
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        if not isinstance(value, (int, float)):
            continue
        metric = OtelMetric(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            service=str(source or "extension")[:255],
            timestamp=now,
            metric_name=f"{source}.{str(key)}"[:255],
            metric_type="gauge",
            value=float(value),
            labels={"extension_config_id": instance_id or "unbound", "source": str(source or "extension")[:100]},
        )
        db.add(metric)
        created += 1

    if instance_id:
        result = await db.execute(
            select(ExtensionConfig).where(
                ExtensionConfig.id == instance_id,
                ExtensionConfig.tenant_id == tenant_id,
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            cfg.last_check = now
            cfg.last_status = "ok" if status == "completed" and not error else "error"
            cfg.last_error = error
            cfg.metrics_collected = (cfg.metrics_collected or 0) + created
            # Best-effort next_run calculation
            try:
                interval = int(cfg.interval_seconds or 300)
            except Exception:
                interval = 300
            cfg.next_run_at = now if interval <= 0 else (now + timedelta(seconds=interval))

    return created
