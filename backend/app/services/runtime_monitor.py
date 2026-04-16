"""Runtime metrics for LAS API instances stored in Redis."""
from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.sentinel import Sentinel

from app.core.config import settings


INSTANCE_ID = os.getenv("API_INSTANCE_ID") or socket.gethostname()
INSTANCE_STARTED_AT = datetime.now(timezone.utc).isoformat()
INSTANCE_KEY = f"las:runtime:instance:{INSTANCE_ID}"
LATENCY_KEY = f"{INSTANCE_KEY}:latency"
LATENCY_WINDOW = 200
TTL_SECONDS = 900

_redis_client: aioredis.Redis | None = None
_redis_sentinel: Sentinel | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        sentinels = []
        if settings.REDIS_SENTINELS:
            for item in settings.REDIS_SENTINELS.split(","):
                item = item.strip()
                if not item:
                    continue
                if ":" in item:
                    host, port = item.rsplit(":", 1)
                    sentinels.append((host.strip(), int(port.strip())))
        if sentinels:
            global _redis_sentinel
            _redis_sentinel = Sentinel(
                sentinels,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            _redis_client = _redis_sentinel.master_for(
                settings.REDIS_MASTER_NAME,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
        else:
            _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    global _redis_client, _redis_sentinel
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
    _redis_sentinel = None


async def register_instance_metadata() -> None:
    redis = await get_redis()
    payload = {
        "instance_id": INSTANCE_ID,
        "hostname": socket.gethostname(),
        "started_at": INSTANCE_STARTED_AT,
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
    }
    await redis.hset(INSTANCE_KEY, mapping=payload)
    await redis.expire(INSTANCE_KEY, TTL_SECONDS)


async def record_request(path: str, method: str, status_code: int, duration_ms: float) -> None:
    try:
        redis = await get_redis()
        now = datetime.now(timezone.utc).isoformat()
        pipe = redis.pipeline()
        pipe.hset(
            INSTANCE_KEY,
            mapping={
                "instance_id": INSTANCE_ID,
                "hostname": socket.gethostname(),
                "started_at": INSTANCE_STARTED_AT,
                "updated_at": now,
                "last_path": path[:200],
                "last_method": method,
                "latency_last_ms": round(duration_ms, 2),
            },
        )
        pipe.hincrby(INSTANCE_KEY, "requests_total", 1)
        if status_code >= 500:
            pipe.hincrby(INSTANCE_KEY, "errors_5xx_total", 1)
        pipe.hincrbyfloat(INSTANCE_KEY, "latency_total_ms", round(duration_ms, 2))
        pipe.lpush(LATENCY_KEY, round(duration_ms, 2))
        pipe.ltrim(LATENCY_KEY, 0, LATENCY_WINDOW - 1)
        pipe.expire(INSTANCE_KEY, TTL_SECONDS)
        pipe.expire(LATENCY_KEY, TTL_SECONDS)
        await pipe.execute()
    except Exception:
        return


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return round(ordered[index], 2)


async def list_instance_metrics() -> list[dict]:
    try:
        redis = await get_redis()
        keys = sorted(await redis.keys("las:runtime:instance:*"))
        items: list[dict] = []
        for key in keys:
            if key.endswith(":latency"):
                continue
            data = await redis.hgetall(key)
            if not data:
                continue
            latency_values = [float(item) for item in await redis.lrange(f"{key}:latency", 0, LATENCY_WINDOW - 1) if item]
            requests_total = _as_int(data.get("requests_total"))
            errors_5xx_total = _as_int(data.get("errors_5xx_total"))
            latency_total_ms = _as_float(data.get("latency_total_ms"))
            items.append(
                {
                    "instance_id": data.get("instance_id") or key.rsplit(":", 1)[-1],
                    "hostname": data.get("hostname"),
                    "version": data.get("version", settings.APP_VERSION),
                    "started_at": data.get("started_at"),
                    "updated_at": data.get("updated_at"),
                    "requests_total": requests_total,
                    "errors_5xx_total": errors_5xx_total,
                    "error_rate_5xx": round((errors_5xx_total / requests_total) * 100, 2) if requests_total else 0.0,
                    "latency_last_ms": _as_float(data.get("latency_last_ms")),
                    "latency_avg_ms": round(latency_total_ms / requests_total, 2) if requests_total else 0.0,
                    "latency_p95_ms": _percentile(latency_values, 0.95),
                    "sample_size": len(latency_values),
                    "last_method": data.get("last_method"),
                    "last_path": data.get("last_path"),
                }
            )
        return items
    except Exception:
        return []


def serialize_metrics(items: list[dict]) -> str:
    return json.dumps(items, ensure_ascii=False)
