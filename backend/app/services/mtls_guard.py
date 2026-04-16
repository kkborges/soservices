from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.config import settings


def require_mtls_request(request: Request) -> None:
    if not settings.MTLS_REQUIRED:
        return
    verified = (request.headers.get("x-client-verify") or "").strip().upper()
    if verified == "SUCCESS":
        return
    raise HTTPException(status_code=403, detail="mTLS client certificate required")
