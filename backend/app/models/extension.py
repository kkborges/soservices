from sqlalchemy import Column, String, Boolean, JSON, ForeignKey, DateTime, Text, Integer
from app.db.base import Base


class Extension(Base):
    """
    Hub de extensões/plugins disponíveis no marketplace.
    """
    __tablename__ = "extensions"

    slug = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(50))   # database|cloud|security|notification|integration
    icon = Column(String(50))
    version = Column(String(20))
    author = Column(String(100))
    homepage = Column(String(500))
    readme = Column(Text)

    # Config schema (JSON Schema format)
    config_schema = Column(JSON, default=dict)

    # Supported collectors / metrics
    metrics = Column(JSON, default=list)
    dashboards = Column(JSON, default=list)   # built-in dashboard templates

    is_official = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    install_count = Column(Integer, default=0)


class ExtensionConfig(Base):
    """
    Tenant-specific configuration for an installed extension.

    Note:
    - One tenant may have multiple instances of the same extension (e.g. many databases).
    - Execution is usually delegated to an online gateway inside the customer network.
    """
    __tablename__ = "extension_configs"

    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    extension_id = Column(String(36), ForeignKey("extensions.id"), nullable=False)
    name = Column(String(255), default="default")  # instance name (db-prod, db-dr, etc.)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, default=dict)   # encrypted connection strings, credentials

    # Execution
    run_on = Column(String(20), default="auto")  # auto|gateway|server|agent (agent reserved)
    gateway_type = Column(String(50))  # agents|integrations|logs|security|control (when run_on uses gateway)
    interval_seconds = Column(Integer, default=300)
    next_run_at = Column(DateTime(timezone=True))

    # Status
    last_check = Column(DateTime(timezone=True))
    last_status = Column(String(20), default="unknown")
    last_error = Column(Text)
    metrics_collected = Column(Integer, default=0)
