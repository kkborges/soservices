"""Enterprise services API endpoints."""
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services import (
    rbac_service,
    audit_logging_service,
    secret_management_service,
    structured_logging_service,
    distributed_tracing_service,
    intelligent_alerting_service,
    self_healing_service,
    multi_region_disaster_recovery_service,
    predictive_analytics_service
)

router = APIRouter(prefix="/enterprise", tags=["enterprise"])

# Pydantic models for request/response
class PermissionRequest(BaseModel):
    """Request model for permission operations."""
    user_id: int
    resource: str = Field(..., description="Resource identifier")
    action: str = Field(..., description="Action to perform")

class AuditLogRequest(BaseModel):
    """Request model for audit logging."""
    user_id: int
    entity_type: str
    entity_id: str
    action: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None

class SecretRequest(BaseModel):
    """Request model for secret management."""
    secret_key: str = Field(..., min_length=1)
    secret_value: str = Field(..., min_length=1)
    description: Optional[str] = None
    ttl: Optional[int] = Field(None, description="Time to live in seconds")

class AlertRuleRequest(BaseModel):
    """Request model for alert rules."""
    name: str
    metric_name: str
    condition: str = Field(..., description="Condition expression (e.g., '> 90')")
    threshold: float
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    channel: str = Field(..., description="Notification channel")
    cooldown_minutes: int = Field(default=5, ge=1)

class TraceRequest(BaseModel):
    """Request model for distributed tracing."""
    service_name: str
    operation_name: str
    tags: Optional[Dict[str, Any]] = None

class BackupRequest(BaseModel):
    """Request model for disaster recovery backup."""
    region: str
    components: Optional[List[str]] = None

# RBAC endpoints
@router.post("/permissions/check")
async def check_permission(
    request: PermissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Check if a user has permission to perform an action on a resource."""
    service = rbac_service.RBACService(db)
    has_permission = await service.check_permission(
        user_id=request.user_id,
        resource=request.resource,
        action=request.action
    )
    return {"has_permission": has_permission, "user_id": request.user_id, "resource": request.resource, "action": request.action}

@router.get("/permissions/user/{user_id}")
async def get_user_permissions(
    user_id: int = Path(..., description="User ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get all permissions for a user."""
    service = rbac_service.RBACService(db)
    permissions = await service.get_user_permissions(user_id)
    return {"user_id": user_id, "permissions": permissions}

# Audit logging endpoints
@router.post("/audit/log")
async def create_audit_log(
    request: AuditLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create an audit log entry."""
    service = audit_logging_service.AuditLoggingService(db)
    entry = await service.log_action(
        user_id=request.user_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        action=request.action,
        details=request.details,
        ip_address=request.ip_address
    )
    return {"success": True, "audit_id": entry.id, "hash": entry.hash}

@router.get("/audit/logs")
async def get_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Query audit logs with filters."""
    service = audit_logging_service.AuditLoggingService(db)
    logs = await service.query_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    return {"logs": logs, "count": len(logs)}

@router.post("/audit/verify")
async def verify_audit_integrity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Verify the integrity of the audit log chain."""
    service = audit_logging_service.AuditLoggingService(db)
    is_valid = await service.verify_integrity()
    return {"is_valid": is_valid, "checked_at": datetime.now(timezone.utc).isoformat()}

# Secret management endpoints
@router.post("/secrets")
async def create_secret(
    request: SecretRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Store a secret securely."""
    service = secret_management_service.SecretManagementService(db)
    secret_id = await service.store_secret(
        secret_key=request.secret_key,
        secret_value=request.secret_value,
        created_by=current_user.id,
        description=request.description,
        ttl=request.ttl
    )
    return {"success": True, "secret_id": secret_id}

@router.get("/secrets/{secret_key}")
async def get_secret(
    secret_key: str = Path(..., description="Secret key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieve a secret value."""
    service = secret_management_service.SecretManagementService(db)
    try:
        value = await service.get_secret(secret_key, accessed_by=current_user.id)
        return {"secret_key": secret_key, "secret_value": value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/secrets/{secret_key}")
async def delete_secret(
    secret_key: str = Path(..., description="Secret key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Delete a secret."""
    service = secret_management_service.SecretManagementService(db)
    success = await service.delete_secret(secret_key)
    if not success:
        raise HTTPException(status_code=404, detail="Secret not found")
    return {"success": True, "secret_key": secret_key}

@router.post("/secrets/rotate/{secret_key}")
async def rotate_secret(
    secret_key: str = Path(..., description="Secret key"),
    new_value: str = Body(..., description="New secret value"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Rotate a secret value."""
    service = secret_management_service.SecretManagementService(db)
    try:
        success = await service.rotate_secret(secret_key, new_value, rotated_by=current_user.id)
        return {"success": success, "secret_key": secret_key}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Distributed tracing endpoints
@router.post("/tracing/span")
async def create_trace_span(
    request: TraceRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new trace span."""
    service = distributed_tracing_service.DistributedTracingService()
    context = service.start_span(
        service_name=request.service_name,
        operation_name=request.operation_name,
        tags=request.tags
    )
    return {
        "trace_id": context["trace_id"],
        "span_id": context["span_id"],
        "service_name": request.service_name,
        "operation_name": request.operation_name
    }

@router.get("/tracing/metrics/{service_name}")
async def get_trace_metrics(
    service_name: str = Path(..., description="Service name"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get aggregated metrics for a service."""
    service = distributed_tracing_service.DistributedTracingService()
    metrics = service.get_service_metrics(service_name)
    return {"service_name": service_name, "metrics": metrics}

# Intelligent alerting endpoints
@router.post("/alerts/rules")
async def create_alert_rule(
    request: AlertRuleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new alert rule."""
    service = intelligent_alerting_service.IntelligentAlertingService(db)
    rule_id = await service.create_rule(
        name=request.name,
        metric_name=request.metric_name,
        condition=request.condition,
        threshold=request.threshold,
        severity=request.severity,
        channel=request.channel,
        cooldown_minutes=request.cooldown_minutes
    )
    return {"success": True, "rule_id": rule_id}

@router.get("/alerts/anomalies")
async def detect_anomalies(
    metric_name: str = Query(..., description="Metric name to analyze"),
    sensitivity: float = Query(2.0, ge=1.0, le=5.0, description="Anomaly detection sensitivity"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Detect anomalies in metric data."""
    service = intelligent_alerting_service.IntelligentAlertingService(db)
    anomalies = await service.detect_anomalies(metric_name, sensitivity)
    return {"metric_name": metric_name, "anomalies": anomalies}

@router.post("/alerts/evaluate/{rule_id}")
async def evaluate_alert_rule(
    rule_id: int = Path(..., description="Alert rule ID"),
    metric_value: float = Body(..., description="Current metric value"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Evaluate an alert rule with a metric value."""
    service = intelligent_alerting_service.IntelligentAlertingService(db)
    result = await service.evaluate_rule(rule_id, metric_value)
    return {"rule_id": rule_id, "triggered": result}

# Self-healing endpoints
@router.post("/healing/remediate")
async def trigger_remediation(
    component: str = Body(..., description="Component to remediate"),
    issue_type: str = Body(..., description="Type of issue"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Trigger automatic remediation for a component."""
    service = self_healing_service.SelfHealingService(db)
    action_taken = await service.auto_remediate(component, issue_type)
    return {
        "component": component,
        "issue_type": issue_type,
        "action_taken": action_taken,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/healing/health/{component}")
async def check_component_health(
    component: str = Path(..., description="Component name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Check health status of a component."""
    service = self_healing_service.SelfHealingService(db)
    health_score = await service.calculate_health_score(component)
    return {
        "component": component,
        "health_score": health_score,
        "status": "healthy" if health_score > 0.7 else "unhealthy"
    }

# Disaster recovery endpoints
@router.post("/recovery/backup")
async def create_backup(
    request: BackupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a backup in specified region."""
    service = multi_region_disaster_recovery_service.MultiRegionDisasterRecoveryService(db)
    backup_id = await service.create_backup(request.region, components=request.components)
    return {"success": True, "backup_id": backup_id, "region": request.region}

@router.post("/recovery/failover")
async def trigger_failover(
    from_region: str = Body(..., description="Source region"),
    to_region: str = Body(..., description="Target region"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Trigger failover from one region to another."""
    service = multi_region_disaster_recovery_service.MultiRegionDisasterRecoveryService(db)
    success = await service.failover(from_region, to_region)
    return {
        "success": success,
        "from_region": from_region,
        "to_region": to_region,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/recovery/health")
async def get_regional_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get health status of all regions."""
    service = multi_region_disaster_recovery_service.MultiRegionDisasterRecoveryService(db)
    health_status = await service.get_regional_health()
    return {"regional_health": health_status, "checked_at": datetime.now(timezone.utc).isoformat()}

# Predictive analytics endpoints
@router.get("/analytics/forecast/{metric_name}")
async def forecast_metric(
    metric_name: str = Path(..., description="Metric to forecast"),
    horizon_hours: int = Query(24, ge=1, le=168, description="Forecast horizon in hours"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Generate forecast for a metric."""
    service = predictive_analytics_service.PredictiveAnalyticsService(db)
    forecast = await service.forecast_metric(metric_name, horizon_hours)
    return {
        "metric_name": metric_name,
        "horizon_hours": horizon_hours,
        "forecast": forecast
    }

@router.get("/analytics/capacity/{resource}")
async def predict_capacity(
    resource: str = Path(..., description="Resource type"),
    days_ahead: int = Query(7, ge=1, le=90, description="Days to predict ahead"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Predict capacity requirements for a resource."""
    service = predictive_analytics_service.PredictiveAnalyticsService(db)
    prediction = await service.predict_capacity_needs(resource, days_ahead)
    return {
        "resource": resource,
        "days_ahead": days_ahead,
        "prediction": prediction
    }

@router.post("/analytics/incident/predict")
async def predict_incident(
    component: str = Body(..., description="Component to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Predict potential incidents for a component."""
    service = predictive_analytics_service.PredictiveAnalyticsService(db)
    prediction = await service.predict_incidents(component)
    return {
        "component": component,
        "incident_probability": prediction,
        "risk_level": "high" if prediction > 0.7 else "medium" if prediction > 0.3 else "low"
    }

# Structured logging endpoints (for testing/debugging)
@router.post("/logging/test")
async def test_structured_logging(
    message: str = Body(..., description="Log message"),
    level: str = Body("info", description="Log level"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test structured logging functionality."""
    logger = structured_logging_service.StructuredLogger("test")
    
    if level == "debug":
        logger.debug(message, user_id=current_user.id)
    elif level == "info":
        logger.info(message, user_id=current_user.id)
    elif level == "warning":
        logger.warning(message, user_id=current_user.id)
    elif level == "error":
        logger.error(message, user_id=current_user.id)
    else:
        raise HTTPException(status_code=400, detail="Invalid log level")
    
    return {"success": True, "message": message, "level": level}