from __future__ import annotations

from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from app.db.base import Base


class LicenseKey(Base):
    """
    Commercial license keys used to unlock entitlements for SaaS and on-prem deployments.

    This table is intentionally simple:
    - SaaS: superadmin generates and assigns keys to a customer tenant.
    - On-prem: the deployment can store the key and optionally validate online against SaaS.
    """

    __tablename__ = "license_keys"

    code = Column(String(255), unique=True, nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    # SaaS | onprem
    edition = Column(String(30), default="saas")
    status = Column(String(20), default="active")  # active|revoked|expired

    expires_at = Column(DateTime(timezone=True), nullable=True)

    # {"infra": true, "complete": true, ...}
    entitlements = Column(JSON, default=dict)
    # {"max_hosts_infra": 50, "max_hosts_full": 10, "max_network_assets": 20, ...}
    limits = Column(JSON, default=dict)

