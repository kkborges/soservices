"""
Enterprise Services Package

Provides production-grade microservices for:
- RBAC (Role-Based Access Control)
- Audit Logging
- Secret Management
- Structured Logging
- Distributed Tracing
- Intelligent Alerting
- Self-Healing
- Disaster Recovery
- Predictive Analytics
"""

# Lazy imports to avoid circular dependency issues
# Import services directly as needed:
#   from app.services.rbac_service import GranularRBACService
#   from app.services.audit_logging_service import AuditLoggingService
#   etc.

__all__ = [
    "GranularRBACService",
    "AuditLoggingService",
    "SecretManagementService",
    "StructuredLoggingService",
    "DistributedTracingService",
    "IntelligentAlertingService",
    "SelfHealingService",
    "MultiRegionDisasterRecoveryService",
    "PredictiveAnalyticsService",
]

__version__ = "1.0.0"
