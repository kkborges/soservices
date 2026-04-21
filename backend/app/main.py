"""
LAS Platform — FastAPI Application Entry Point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time

from app.core.config import settings
from app.db.base import init_db
from app.api.v1.router import api_router
from app.services.runtime_monitor import close_redis, record_request, register_instance_metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    await register_instance_metadata()
    yield
    await close_redis()
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="LAS Plataforma de Monitoramento de Infraestrutura e Observabilidade",
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    response = None
    try:
        response = await call_next(request)
    finally:
        process_time = (time.time() - start_time) * 1000
        status_code = response.status_code if response is not None else 500
        await record_request(request.url.path, request.method, status_code, process_time)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response


# ── Routes ─────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "service": settings.APP_NAME,
    }


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION}", "docs": "/api/docs"}


# ── Exception handlers ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )
