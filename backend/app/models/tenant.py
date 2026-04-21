from sqlalchemy import Column, String, Integer, Boolean, JSON, Text, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class PlanType(str, enum.Enum):
    trial = "trial"
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class Tenant(Base):
    """Customer tenant with licensing, limits, feature flags and platform settings."""

    __tablename__ = "tenants"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    plan = Column(Enum(PlanType), default=PlanType.trial)
    status = Column(String(20), default="active")
    admin_email = Column(String(255))
    admin_name = Column(String(255))

    # Limits
    max_hosts = Column(Integer, default=10)
    max_agents = Column(Integer, default=10)
    max_users = Column(Integer, default=5)
    max_synthetic_tests = Column(Integer, default=20)

    # AI config
    ai_provider = Column(String(30), default="openai")
    ai_api_key = Column(Text)       # tenant's own key (encrypted)
    ai_model = Column(String(50))

    # Feature flags
    features = Column(JSON, default=dict)
    settings = Column(JSON, default=dict)

    # License
    license_key = Column(String(255))
    license_expires_at = Column(String(30))

    users = relationship("User", back_populates="tenant", lazy="selectin")
    agents = relationship("AgentToken", back_populates="tenant", lazy="selectin")

    @property
    def is_active(self) -> bool:
        """Compatibility alias derived from tenant status."""
        return self.status == "active"

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = "active" if value else "inactive"
