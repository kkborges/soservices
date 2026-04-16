"""
AI-Powered Intelligent Alerting System

Provides:
- Real-time alert generation from metrics/logs
- Smart alert correlation and deduplication
- Intelligent escalation based on severity and patterns
- Alert clustering and noise reduction
- Machine learning for false positive detection
- Multi-channel notification (email, Slack, PagerDuty, SMS)
- Alert aggregation and suppression
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4
import json


# ============================================================================
# Alert Enums
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"


class AlertStatus(str, Enum):
    """Alert lifecycle status"""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    SILENCED = "silenced"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    WEBHOOK = "webhook"
    TEAMS = "teams"
    OPSGENIE = "opsgenie"


class AlertType(str, Enum):
    """Types of alerts"""
    THRESHOLD_BREACH = "threshold_breach"
    ANOMALY_DETECTION = "anomaly_detection"
    PATTERN_MATCH = "pattern_match"
    SLA_VIOLATION = "sla_violation"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_ISSUE = "compliance_issue"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CUSTOM = "custom"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class AlertMetadata:
    """Alert metadata"""
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    alert_type: AlertType = AlertType.CUSTOM
    source: str = ""  # monitoring system, application, etc.
    severity: AlertSeverity = AlertSeverity.WARNING
    
    # Timing
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Status
    status: AlertStatus = AlertStatus.TRIGGERED
    
    # Correlation
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    group_id: Optional[str] = None  # For clustering similar alerts
    
    # Owner/Responsibility
    assigned_to: Optional[str] = None
    team: Optional[str] = None


@dataclass
class AlertContext:
    """Contextual information for alert"""
    tenant_id: str
    resource_type: str
    resource_id: str
    metric_name: str
    metric_value: float
    threshold: float
    baseline: Optional[float] = None
    
    # Environment
    service: Optional[str] = None
    region: Optional[str] = None
    environment: Optional[str] = None
    
    # Additional context
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Alert definition rule"""
    rule_id: str
    name: str
    description: str
    enabled: bool
    
    alert_type: AlertType
    severity: AlertSeverity
    
    # Trigger conditions
    metric_name: str
    operator: str  # "greater_than", "less_than", "equals", "anomaly"
    threshold: float
    
    # Window and aggregation
    evaluation_window_sec: int = 60
    aggregation: str = "avg"  # avg, max, min, sum
    
    # Cooldown to prevent alert spam
    cooldown_minutes: int = 5
    
    # Suppression windows
    suppression_windows: List[Tuple[str, str]] = field(default_factory=list)  # (start_time, end_time)
    
    # Notification settings
    channels: List[NotificationChannel] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    
    # Escalation
    escalation_enabled: bool = False
    escalation_minutes: int = 30
    
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AlertInstance:
    """Individual alert instance"""
    metadata: AlertMetadata
    context: AlertContext
    rule: AlertRule
    
    message: str
    description: str
    
    # ML scoring for importance
    confidence_score: float = 1.0  # 0.0-1.0
    is_anomaly: bool = False
    is_duplicate: bool = False
    is_suppressed: bool = False
    
    # Notifications sent
    notifications_sent: List[Tuple[NotificationChannel, datetime]] = field(default_factory=list)


# ============================================================================
# Intelligent Alerting Service
# ============================================================================

class IntelligentAlertingService:
    """
    AI-Powered Intelligent Alerting System
    
    Features:
    - Real-time alert generation from various sources
    - Intelligent correlation and deduplication
    - ML-based false positive detection
    - Smart escalation based on patterns
    - Alert clustering and noise reduction
    - Multi-channel notifications
    """

    def __init__(self):
        # Storage
        self._alerts: Dict[str, AlertInstance] = {}
        self._rules: Dict[str, AlertRule] = {}
        self._alert_history: List[AlertInstance] = []
        
        # Deduplication/Correlation
        self._alert_fingerprints: Dict[str, str] = {}  # fingerprint -> alert_id
        self._recent_alerts: Dict[str, datetime] = {}  # cooldown tracking
        
        # ML/Analytics
        self._baseline_metrics: Dict[str, float] = {}
        self._anomaly_detector = AnomalyDetector()
        
        # Subscribers
        self._alert_subscribers: List[callable] = []

    # ========================================================================
    # Alert Creation and Management
    # ========================================================================

    async def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        source: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        message: str,
        description: str,
        metric_name: str = "",
        metric_value: float = 0.0,
        threshold: float = 0.0,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AlertInstance]:
        """Create and process new alert"""
        
        # Create alert metadata
        alert_metadata = AlertMetadata(
            alert_type=alert_type,
            source=source,
            severity=severity
        )
        
        # Create context
        context = AlertContext(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        # Create dummy rule (would be looked up in production)
        rule = AlertRule(
            rule_id=f"rule_{alert_type.value}",
            name=f"{alert_type.value} Rule",
            description=f"Auto rule for {alert_type.value}",
            enabled=True,
            alert_type=alert_type,
            severity=severity,
            metric_name=metric_name,
            operator="greater_than",
            threshold=threshold,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK]
        )
        
        # Create alert instance
        alert = AlertInstance(
            metadata=alert_metadata,
            context=context,
            rule=rule,
            message=message,
            description=description
        )
        
        # Apply intelligent processing
        alert = await self._process_alert(alert)
        
        if alert:
            self._alerts[alert.metadata.alert_id] = alert
            self._alert_history.append(alert)
            
            # Notify subscribers
            await self._notify_alert(alert)
        
        return alert

    async def _process_alert(self, alert: AlertInstance) -> Optional[AlertInstance]:
        """Apply intelligent processing to alert"""
        
        # Check for duplicate
        if await self._is_duplicate(alert):
            alert.metadata.status = AlertStatus.SUPPRESSED
            alert.is_duplicate = True
            return alert
        
        # Check cooldown
        if await self._in_cooldown(alert):
            alert.is_suppressed = True
            return alert
        
        # Anomaly detection
        if alert.context.metric_value > 0:
            is_anomaly, confidence = await self._detect_anomaly(alert)
            alert.is_anomaly = is_anomaly
            alert.confidence_score = confidence
        
        # Check suppression windows
        if self._is_in_suppression_window(alert.rule):
            alert.metadata.status = AlertStatus.SILENCED
            alert.is_suppressed = True
        
        return alert

    # ========================================================================
    # Deduplication and Correlation
    # ========================================================================

    async def _is_duplicate(self, alert: AlertInstance) -> bool:
        """Detect if alert is duplicate of recent alert"""
        
        fingerprint = self._compute_fingerprint(alert)
        
        # Check recent alerts
        if fingerprint in self._alert_fingerprints:
            recent_alert_id = self._alert_fingerprints[fingerprint]
            recent_alert = self._alerts.get(recent_alert_id)
            
            if recent_alert:
                time_diff = datetime.utcnow() - recent_alert.metadata.triggered_at
                if time_diff < timedelta(minutes=alert.rule.cooldown_minutes):
                    return True
        
        self._alert_fingerprints[fingerprint] = alert.metadata.alert_id
        return False

    async def _in_cooldown(self, alert: AlertInstance) -> bool:
        """Check if alert is in cooldown period"""
        
        fingerprint = self._compute_fingerprint(alert)
        
        if fingerprint in self._recent_alerts:
            last_alert_time = self._recent_alerts[fingerprint]
            time_diff = datetime.utcnow() - last_alert_time
            
            if time_diff < timedelta(minutes=alert.rule.cooldown_minutes):
                return True
        
        self._recent_alerts[fingerprint] = datetime.utcnow()
        return False

    def _compute_fingerprint(self, alert: AlertInstance) -> str:
        """Compute fingerprint for deduplication"""
        
        fingerprint_data = {
            "alert_type": alert.metadata.alert_type.value,
            "resource_type": alert.context.resource_type,
            "resource_id": alert.context.resource_id,
            "severity": alert.metadata.severity.value
        }
        
        import hashlib
        data_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    # ========================================================================
    # Anomaly Detection
    # ========================================================================

    async def _detect_anomaly(
        self,
        alert: AlertInstance
    ) -> Tuple[bool, float]:
        """Detect if alert represents anomalous behavior"""
        
        # This would integrate with ML model in production
        is_anomaly, confidence = self._anomaly_detector.detect(
            alert.context.metric_name,
            alert.context.metric_value,
            alert.context.baseline
        )
        
        return is_anomaly, confidence

    # ========================================================================
    # Escalation
    # ========================================================================

    async def escalate_alert(
        self,
        alert_id: str,
        reason: str,
        escalate_to: Optional[List[str]] = None
    ) -> bool:
        """Escalate alert"""
        
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.metadata.status = AlertStatus.ESCALATED
        
        if escalate_to:
            # Send notifications to escalation recipients
            await self._send_notifications(
                alert,
                escalate_to,
                severity=AlertSeverity.CRITICAL
            )
        
        return True

    # ========================================================================
    # Acknowledgment and Resolution
    # ========================================================================

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        note: Optional[str] = None
    ) -> bool:
        """Acknowledge alert"""
        
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.metadata.status = AlertStatus.ACKNOWLEDGED
        alert.metadata.acknowledged_at = datetime.utcnow()
        alert.metadata.assigned_to = acknowledged_by
        
        return True

    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        resolution: str
    ) -> bool:
        """Mark alert as resolved"""
        
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.metadata.status = AlertStatus.RESOLVED
        alert.metadata.resolved_at = datetime.utcnow()
        
        return True

    # ========================================================================
    # Notification Management
    # ========================================================================

    async def _send_notifications(
        self,
        alert: AlertInstance,
        recipients: Optional[List[str]] = None,
        severity: Optional[AlertSeverity] = None
    ) -> None:
        """Send notifications via configured channels"""
        
        target_recipients = recipients or alert.rule.recipients
        target_channels = alert.rule.channels
        target_severity = severity or alert.metadata.severity
        
        for channel in target_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    await self._send_email(alert, target_recipients)
                elif channel == NotificationChannel.SLACK:
                    await self._send_slack(alert)
                elif channel == NotificationChannel.PAGERDUTY:
                    await self._send_pagerduty(alert)
                elif channel == NotificationChannel.SMS:
                    if target_severity in [AlertSeverity.CRITICAL, AlertSeverity.CATASTROPHIC]:
                        await self._send_sms(alert, target_recipients)
                
                alert.notifications_sent.append((channel, datetime.utcnow()))
            except Exception:
                pass  # Continue with other channels

    async def _send_email(self, alert: AlertInstance, recipients: List[str]) -> None:
        """Send email notification"""
        # Implementation would integrate with email service
        pass

    async def _send_slack(self, alert: AlertInstance) -> None:
        """Send Slack notification"""
        # Implementation would integrate with Slack API
        pass

    async def _send_pagerduty(self, alert: AlertInstance) -> None:
        """Send PagerDuty notification"""
        # Implementation would integrate with PagerDuty API
        pass

    async def _send_sms(self, alert: AlertInstance, recipients: List[str]) -> None:
        """Send SMS notification"""
        # Implementation would integrate with SMS service
        pass

    # ========================================================================
    # Suppression Windows
    # ========================================================================

    def _is_in_suppression_window(self, rule: AlertRule) -> bool:
        """Check if current time is in suppression window"""
        
        current_time = datetime.utcnow().strftime("%H:%M")
        
        for start, end in rule.suppression_windows:
            if start <= current_time <= end:
                return True
        
        return False

    async def add_suppression_window(
        self,
        rule_id: str,
        start_time: str,  # HH:MM format
        end_time: str
    ) -> bool:
        """Add suppression window to rule"""
        
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        rule.suppression_windows.append((start_time, end_time))
        return True

    # ========================================================================
    # Rule Management
    # ========================================================================

    async def create_alert_rule(
        self,
        name: str,
        description: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        metric_name: str,
        operator: str,
        threshold: float,
        channels: List[NotificationChannel],
        recipients: List[str]
    ) -> AlertRule:
        """Create alert rule"""
        
        rule = AlertRule(
            rule_id=f"rule_{uuid4().hex[:8]}",
            name=name,
            description=description,
            enabled=True,
            alert_type=alert_type,
            severity=severity,
            metric_name=metric_name,
            operator=operator,
            threshold=threshold,
            channels=channels,
            recipients=recipients
        )
        
        self._rules[rule.rule_id] = rule
        return rule

    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule"""
        return self._rules.get(rule_id)

    async def list_rules(self, enabled_only: bool = True) -> List[AlertRule]:
        """List alert rules"""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    # ========================================================================
    # Query and Analytics
    # ========================================================================

    async def get_alert(self, alert_id: str) -> Optional[AlertInstance]:
        """Get alert"""
        return self._alerts.get(alert_id)

    async def list_alerts(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100
    ) -> List[AlertInstance]:
        """List alerts with filters"""
        
        alerts = list(self._alerts.values())
        
        if tenant_id:
            alerts = [a for a in alerts if a.context.tenant_id == tenant_id]
        
        if status:
            alerts = [a for a in alerts if a.metadata.status == status]
        
        if severity:
            alerts = [a for a in alerts if a.metadata.severity == severity]
        
        return alerts[-limit:]

    async def get_alert_count_by_severity(
        self,
        tenant_id: str
    ) -> Dict[str, int]:
        """Get alert count by severity"""
        
        alerts = [
            a for a in self._alerts.values()
            if a.context.tenant_id == tenant_id
        ]
        
        counts = {}
        for severity in AlertSeverity:
            counts[severity.value] = len([
                a for a in alerts
                if a.metadata.severity == severity
            ])
        
        return counts

    # ========================================================================
    # Alerting Subscribers
    # ========================================================================

    def subscribe(self, callback: callable) -> None:
        """Subscribe to alerts"""
        self._alert_subscribers.append(callback)

    async def _notify_alert(self, alert: AlertInstance) -> None:
        """Notify subscribers of alert"""
        
        for subscriber in self._alert_subscribers:
            try:
                if hasattr(subscriber, "__await__"):
                    await subscriber(alert)
                else:
                    subscriber(alert)
            except Exception:
                pass


# ============================================================================
# Anomaly Detector
# ============================================================================

class AnomalyDetector:
    """Simple ML-based anomaly detector"""

    def __init__(self):
        self._baselines: Dict[str, float] = {}
        self._std_devs: Dict[str, float] = {}

    def detect(
        self,
        metric_name: str,
        value: float,
        baseline: Optional[float] = None
    ) -> Tuple[bool, float]:
        """Detect anomaly in metric value"""
        
        if not baseline and metric_name not in self._baselines:
            return False, 0.5
        
        baseline = baseline or self._baselines.get(metric_name, value)
        std_dev = self._std_devs.get(metric_name, baseline * 0.1)
        
        # Z-score based detection
        z_score = abs((value - baseline) / std_dev) if std_dev > 0 else 0
        
        # Anomaly if z-score > 3
        is_anomaly = z_score > 3.0
        
        # Confidence based on z-score
        confidence = min(z_score / 3.0, 1.0)
        
        return is_anomaly, confidence

    def update_baseline(self, metric_name: str, value: float) -> None:
        """Update baseline for metric"""
        self._baselines[metric_name] = value
