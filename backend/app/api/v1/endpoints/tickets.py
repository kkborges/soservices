"""Ticket management for tenants and platform administrators."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.middleware.auth import get_current_user
from app.models import Ticket, TicketMessage, User
from app.services.ticket_ai_service import analyze_ticket_with_ai

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreatePayload(BaseModel):
    title: str
    category: str = "incident"
    severity: str = "medium"
    environment: str | None = None
    service_name: str | None = None
    description: str
    log_collection_notes: str | None = None
    attachments: list[dict] = []


class TicketReplyPayload(BaseModel):
    message: str
    status: str | None = None
    is_internal: bool = False


@router.get("")
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Ticket)
        .where(Ticket.tenant_id == user.tenant_id)
        .order_by(desc(Ticket.updated_at), desc(Ticket.created_at))
    )
    tickets = result.scalars().all()
    return [
        {
            "id": ticket.id,
            "title": ticket.title,
            "category": ticket.category,
            "severity": ticket.severity,
            "status": ticket.status,
            "service_name": ticket.service_name,
            "created_at": ticket.created_at,
            "ai_status": ticket.ai_status,
            "ai_summary": ticket.ai_summary,
        }
        for ticket in tickets
    ]


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages_result = await db.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at)
    )
    return {
        "ticket": {
            "id": ticket.id,
            "title": ticket.title,
            "category": ticket.category,
            "severity": ticket.severity,
            "status": ticket.status,
            "environment": ticket.environment,
            "service_name": ticket.service_name,
            "description": ticket.description,
            "log_collection_notes": ticket.log_collection_notes,
            "ai_summary": ticket.ai_summary,
            "ai_suspected_cause": ticket.ai_suspected_cause,
            "ai_recommended_actions": ticket.ai_recommended_actions,
            "ai_confidence": ticket.ai_confidence,
            "ai_status": ticket.ai_status,
        },
        "messages": [
            {
                "id": msg.id,
                "author_role": msg.author_role,
                "message": msg.message,
                "is_internal": msg.is_internal,
                "created_at": msg.created_at,
            }
            for msg in messages_result.scalars().all()
        ],
    }


@router.post("")
async def create_ticket(
    payload: TicketCreatePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = Ticket(
        id=str(uuid4()),
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=payload.title,
        category=payload.category,
        severity=payload.severity,
        environment=payload.environment,
        service_name=payload.service_name,
        description=payload.description,
        log_collection_notes=payload.log_collection_notes,
        status="open",
    )
    db.add(ticket)
    db.add(
        TicketMessage(
            id=str(uuid4()),
            ticket_id=ticket.id,
            tenant_id=user.tenant_id,
            author_id=user.id,
            author_role=user.role,
            message=payload.description,
            is_internal=False,
            attachments=payload.attachments,
        )
    )
    await db.flush()

    ai_result = await analyze_ticket_with_ai(
        {
            "title": payload.title,
            "category": payload.category,
            "severity": payload.severity,
            "environment": payload.environment,
            "service_name": payload.service_name,
            "description": payload.description,
            "log_collection_notes": payload.log_collection_notes,
            "attachments": payload.attachments,
        }
    )
    ticket.ai_status = ai_result.get("status", "failed")
    ticket.ai_summary = ai_result.get("summary")
    ticket.ai_suspected_cause = ai_result.get("suspected_cause")
    ticket.ai_recommended_actions = ai_result.get("recommended_actions")
    ticket.ai_confidence = ai_result.get("confidence", 0)
    ticket.ai_model = ai_result.get("model")
    ticket.ai_payload = ai_result
    if ticket.ai_status == "completed":
        ticket.status = "triaged"

    await db.commit()
    return {"status": "created", "ticket_id": ticket.id, "ai_status": ticket.ai_status}


@router.post("/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: str,
    payload: TicketReplyPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.add(
        TicketMessage(
            id=str(uuid4()),
            ticket_id=ticket.id,
            tenant_id=user.tenant_id,
            author_id=user.id,
            author_role=user.role,
            message=payload.message,
            is_internal=payload.is_internal,
        )
    )
    if payload.status:
        ticket.status = payload.status
    if payload.status == "resolved":
        ticket.resolved_at = datetime.now(timezone.utc)
    if not ticket.first_response_at:
        ticket.first_response_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "updated"}
