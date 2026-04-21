from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    """Tenant user account with local authentication and session metadata."""

    __tablename__ = "users"

    def __init__(self, **kwargs):
        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password is not None:
            self.password = password
        if not self.username and self.email:
            self.username = self.email.split("@", 1)[0]
        if not self.password_hash:
            from app.services.auth_service import hash_password

            self.password_hash = hash_password(f"disabled:{self.id or self.email or self.username}")

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    username = Column(String(100), nullable=True)
    email = Column(String(255), nullable=False)
    full_name = Column(String(255))
    password_hash = Column(String(255), nullable=True)
    role = Column(String(30), default="viewer")   # superadmin|admin|operator|viewer
    active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(100))
    last_login = Column(DateTime(timezone=True))
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    avatar_url = Column(String(500))

    tenant = relationship("Tenant", foreign_keys=[tenant_id], back_populates="users", lazy="selectin")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        """Compatibility alias for active users."""
        return bool(self.active)

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value

    @property
    def password(self) -> str | None:
        """Compatibility alias exposing the stored password hash."""
        return self.password_hash

    @password.setter
    def password(self, value: str) -> None:
        from app.services.auth_service import hash_password

        self.password_hash = hash_password(value)


class Session(Base):
    """Authenticated browser/API session linked to a user and tenant."""

    __tablename__ = "sessions"

    token = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True))
    active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")
