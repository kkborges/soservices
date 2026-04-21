from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey, DateTime, Text
from app.db.base import Base


class Ticket(Base):
    """Customer support ticket enriched with AI analysis and remediation workflow."""

    __tablename__ = "tickets"

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    category = Column(String(100), default="incident")
    severity = Column(String(20), default="medium")
    priority = Column(Integer, default=3)
    status = Column(String(20), default="open")  # open|triaged|in_progress|waiting_customer|resolved|closed
    source = Column(String(30), default="portal")

    environment = Column(String(50))
    service_name = Column(String(255))
    description = Column(Text, nullable=False)
    log_collection_notes = Column(Text)

    ai_summary = Column(Text)
    ai_suspected_cause = Column(Text)
    ai_recommended_actions = Column(Text)
    ai_model = Column(String(100))
    ai_confidence = Column(Integer, default=0)
    ai_status = Column(String(20), default="pending")  # pending|completed|unavailable|failed
    ai_payload = Column(JSON, default=dict)

    first_response_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))


class TicketMessage(Base):
    """Conversation entry, attachment reference or internal note attached to a ticket."""

    __tablename__ = "ticket_messages"

    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    author_role = Column(String(30), default="customer")
    is_internal = Column(Boolean, default=False)
    message = Column(Text, nullable=False)
    attachments = Column(JSON, default=list)
