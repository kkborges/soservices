from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, ForeignKey, DateTime, Text
from app.db.base import Base


class RumSession(Base):
    __tablename__ = "rum_sessions"

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    application = Column(String(255), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(255))
    ip_address = Column(String(50))
    user_agent = Column(Text)
    browser = Column(String(100))
    os = Column(String(100))
    country = Column(String(100))
    region = Column(String(100))
    city = Column(String(100))
    started_at = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    live = Column(Boolean, default=True)
    satisfaction_index = Column(Float, default=100)
    requests_total = Column(Integer, default=0)
    actions_total = Column(Integer, default=0)
    errors_total = Column(Integer, default=0)


class RumEvent(Base):
    __tablename__ = "rum_events"

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    application = Column(String(255), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    name = Column(String(500))
    url = Column(String(2000))
    method = Column(String(20))
    status_code = Column(Integer)
    duration_ms = Column(Float)
    server_time_ms = Column(Float)
    network_time_ms = Column(Float)
    client_time_ms = Column(Float)
    trace_id = Column(String(100), index=True)
    span_id = Column(String(100), index=True)
    service = Column(String(255), index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    satisfied = Column(Boolean, default=True)
    event_metadata = Column("metadata", JSON, default=dict)
