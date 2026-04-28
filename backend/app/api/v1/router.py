"""API v1 router — aggregates all endpoint modules."""
from fastapi import APIRouter
from app.api.v1.endpoints import agents, auth, edge, ingest, licenses, management, platform, tickets, enterprise, trial

api_router = APIRouter()

# Public ingest (token-authenticated, no session needed)
api_router.include_router(ingest.router)

# Session authentication / bootstrap
api_router.include_router(auth.router)

# Agent management (session-authenticated)
api_router.include_router(agents.router)

# Frontend operational endpoints
api_router.include_router(platform.router)
api_router.include_router(management.router)
api_router.include_router(tickets.router)
api_router.include_router(licenses.router)
api_router.include_router(edge.router)

# Enterprise services (session-authenticated)
api_router.include_router(enterprise.router)
api_router.include_router(trial.router)
