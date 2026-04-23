"""
Async runner for Celery worker processes.

Problem:
- Our Celery tasks use SQLAlchemy AsyncEngine (asyncpg) and must run in an asyncio loop.
- Creating a new event loop per task (and closing it) causes asyncpg pooled connections
  to be bound to different loops, triggering errors like:
    "got Future ... attached to a different loop"

Solution:
- Keep a single event loop per worker process (thread-local) and reuse it for all tasks.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

_local = threading.local()


def run_async(coro: Any):
    loop = getattr(_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _local.loop = loop
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

