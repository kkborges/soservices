import secrets

from sqlalchemy import Column, String, Boolean, JSON, ForeignKey, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base


class AgentToken(Base):
    """Installer/runtime token used to register agents and gateways for a tenant."""

    __tablename__ = "agent_tokens"

    def __init__(self, **kwargs):
        agent_type = kwargs.pop("agent_type", None)
        status = kwargs.pop("status", None)
        version = kwargs.pop("version", None)
        last_heartbeat = kwargs.pop("last_heartbeat", None)
        super().__init__(**kwargs)
        if agent_type is not None:
            self.role = agent_type
        config = dict(self.install_config or {})
        if status is not None:
            config["status"] = status
        if version is not None:
            config["version"] = version
        if last_heartbeat is not None:
            config["last_heartbeat"] = last_heartbeat.isoformat() if hasattr(last_heartbeat, "isoformat") else last_heartbeat
        self.install_config = config

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True, default=lambda: f"lsa_{secrets.token_urlsafe(24)}")
    name = Column(String(255))
    description = Column(Text)
    role = Column(String(30), default="agent")   # agent|gateway|ids|otel|apm
    active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))
    last_used = Column(DateTime(timezone=True))
    used_count = Column(Integer, default=0)
    bound_host_id = Column(String(36), ForeignKey("hosts.id"), nullable=True)
    bound_ip = Column(String(50))

    # Config to embed into installer script
    install_config = Column(JSON, default=dict)

    tenant = relationship("Tenant", foreign_keys=[tenant_id], back_populates="agents", lazy="selectin")

    @property
    def agent_type(self) -> str:
        """Compatibility alias for token role."""
        return self.role

    @agent_type.setter
    def agent_type(self, value: str) -> None:
        self.role = value

    @property
    def status(self) -> str:
        """Compatibility status stored in install_config for lightweight tests/views."""
        return (self.install_config or {}).get("status", "offline")

    @status.setter
    def status(self, value: str) -> None:
        config = dict(self.install_config or {})
        config["status"] = value
        self.install_config = config

    @property
    def version(self) -> str | None:
        """Compatibility version stored in install_config."""
        return (self.install_config or {}).get("version")

    @version.setter
    def version(self, value: str | None) -> None:
        config = dict(self.install_config or {})
        config["version"] = value
        self.install_config = config

    @property
    def last_heartbeat(self):
        """Compatibility heartbeat timestamp stored in install_config."""
        return (self.install_config or {}).get("last_heartbeat")

    @last_heartbeat.setter
    def last_heartbeat(self, value) -> None:
        config = dict(self.install_config or {})
        config["last_heartbeat"] = value.isoformat() if hasattr(value, "isoformat") else value
        self.install_config = config
