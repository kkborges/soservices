"""
Self-Healing Capabilities for Nexus Platform

Provides:
- Automatic failure detection and recovery
- Self-diagnosing unhealthy services
- Automatic remediation workflows
- Circuit breaker patterns
- Retry strategies with exponential backoff
- Automatic scaling based on demand
- Health check automation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Coroutine
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4
import asyncio
import random


# ============================================================================
# Self-Healing Enums
# ============================================================================

class RemediationAction(str, Enum):
    """Types of remediation actions"""
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    CLEAR_CACHE = "clear_cache"
    DATABASE_REPAIR = "database_repair"
    CONNECTION_RESET = "connection_reset"
    MEMORY_CLEANUP = "memory_cleanup"
    LOG_FLUSH = "log_flush"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    RECONNECT = "reconnect"
    ROLLBACK = "rollback"


class HealthStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    CRITICAL = "critical"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class HealthCheck:
    """Health check configuration"""
    check_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    service: str = ""
    endpoint: str = ""
    interval_sec: int = 30
    timeout_sec: int = 5
    enabled: bool = True
    
    # Thresholds
    success_threshold: int = 1  # Consecutive successes to mark healthy
    failure_threshold: int = 3  # Consecutive failures to mark unhealthy
    
    # Custom check function
    custom_check: Optional[Callable] = None


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    check_id: str
    service: str
    timestamp: datetime
    status: HealthStatus
    response_time_ms: float
    
    # Details
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    error: Optional[str] = None
    error_type: Optional[str] = None


@dataclass
class RemediationPolicy:
    """Policy defining remediation actions"""
    policy_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    condition: str = ""  # e.g., "memory_usage > 80%"
    
    # Trigger
    trigger_threshold: float = 0.0
    trigger_consecutive_failures: int = 3
    
    # Actions
    actions: List[RemediationAction] = field(default_factory=list)
    action_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Cooldown
    cooldown_minutes: int = 10
    max_actions_per_day: int = 24


@dataclass
class CircuitBreaker:
    """Circuit breaker for dependency failures"""
    service_name: str
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    
    failure_count: int = 0
    success_count: int = 0
    failure_threshold: int = 5
    success_threshold: int = 2
    
    timeout_sec: int = 60
    last_state_change: datetime = field(default_factory=datetime.utcnow)
    
    metrics: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Self-Healing Service
# ============================================================================

class SelfHealingService:
    """
    Self-Healing Capabilities Service
    
    Features:
    - Automatic health monitoring
    - Intelligent failure detection and diagnosis
    - Automatic remediation with configurable policies
    - Circuit breaker for cascading failures
    - Retry logic with exponential backoff
    - Learning from past incidents
    """

    def __init__(self):
        # Health monitoring
        self._health_checks: Dict[str, HealthCheck] = {}
        self._health_status: Dict[str, HealthStatus] = {}
        self._health_history: List[HealthCheckResult] = []
        self._check_results: Dict[str, HealthCheckResult] = {}
        
        # Remediation
        self._remediation_policies: Dict[str, RemediationPolicy] = {}
        self._remediation_history: List[Dict[str, Any]] = []
        self._last_remediation: Dict[str, datetime] = {}  # service -> last action time
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None

    # ========================================================================
    # Health Check Registration
    # ========================================================================

    def register_health_check(
        self,
        name: str,
        service: str,
        endpoint: str,
        interval_sec: int = 30,
        timeout_sec: int = 5,
        custom_check: Optional[Callable] = None
    ) -> str:
        """Register health check"""
        
        check = HealthCheck(
            name=name,
            service=service,
            endpoint=endpoint,
            interval_sec=interval_sec,
            timeout_sec=timeout_sec,
            custom_check=custom_check,
            enabled=True
        )
        
        self._health_checks[check.check_id] = check
        self._health_status[service] = HealthStatus.HEALTHY
        
        return check.check_id

    def unregister_health_check(self, check_id: str) -> bool:
        """Unregister health check"""
        if check_id in self._health_checks:
            del self._health_checks[check_id]
            return True
        return False

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    async def perform_health_check(
        self,
        check_id: str
    ) -> Optional[HealthCheckResult]:
        """Execute health check"""
        
        check = self._health_checks.get(check_id)
        if not check or not check.enabled:
            return None
        
        start_time = datetime.utcnow()
        
        try:
            # Execute custom check if provided
            if check.custom_check:
                status = await self._execute_custom_check(check)
            else:
                # Default HTTP health check
                status = await self._perform_http_check(check)
            
            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = HealthCheckResult(
                check_id=check_id,
                service=check.service,
                timestamp=datetime.utcnow(),
                status=status,
                response_time_ms=response_time_ms,
                message=f"Health check {'passed' if status == HealthStatus.HEALTHY else 'failed'}"
            )
            
        except Exception as e:
            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                check_id=check_id,
                service=check.service,
                timestamp=datetime.utcnow(),
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
                error_type=type(e).__name__,
                message="Health check failed"
            )
        
        # Store result
        self._check_results[check_id] = result
        self._health_history.append(result)
        
        # Update service health status
        await self._update_health_status(check.service, result)
        
        return result

    async def _execute_custom_check(self, check: HealthCheck) -> HealthStatus:
        """Execute custom health check"""
        if check.custom_check:
            result = check.custom_check()
            if asyncio.iscoroutine(result):
                result = await result
            return HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
        return HealthStatus.HEALTHY

    async def _perform_http_check(self, check: HealthCheck) -> HealthStatus:
        """Perform HTTP health check"""
        # This would make actual HTTP request in production
        import random
        # Simulate: 90% success rate
        return HealthStatus.HEALTHY if random.random() > 0.1 else HealthStatus.UNHEALTHY

    async def _update_health_status(
        self,
        service: str,
        result: HealthCheckResult
    ) -> None:
        """Update service health status"""
        
        current_status = self._health_status.get(service, HealthStatus.HEALTHY)
        
        # State machine for health transitions
        if result.status == HealthStatus.HEALTHY:
            if current_status == HealthStatus.DEGRADED:
                self._health_status[service] = HealthStatus.HEALTHY
            elif current_status == HealthStatus.RECOVERING:
                self._health_status[service] = HealthStatus.HEALTHY
        else:
            if current_status == HealthStatus.HEALTHY:
                self._health_status[service] = HealthStatus.DEGRADED
            elif current_status == HealthStatus.DEGRADED:
                self._health_status[service] = HealthStatus.UNHEALTHY
        
        # Trigger remediation if needed
        if self._health_status[service] in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            await self._trigger_remediation(service, result)

    # ========================================================================
    # Remediation
    # ========================================================================

    def create_remediation_policy(
        self,
        name: str,
        condition: str,
        actions: List[RemediationAction],
        trigger_threshold: float = 0.0,
        trigger_consecutive_failures: int = 3,
        cooldown_minutes: int = 10
    ) -> str:
        """Create remediation policy"""
        
        policy = RemediationPolicy(
            name=name,
            condition=condition,
            actions=actions,
            trigger_threshold=trigger_threshold,
            trigger_consecutive_failures=trigger_consecutive_failures,
            cooldown_minutes=cooldown_minutes
        )
        
        self._remediation_policies[policy.policy_id] = policy
        return policy.policy_id

    async def _trigger_remediation(
        self,
        service: str,
        health_result: HealthCheckResult
    ) -> None:
        """Trigger remediation for unhealthy service"""
        
        # Check cooldown
        if service in self._last_remediation:
            time_since_last = datetime.utcnow() - self._last_remediation[service]
            # Get cooldown from policies
            for policy in self._remediation_policies.values():
                if policy.cooldown_minutes > 0:
                    if time_since_last < timedelta(minutes=policy.cooldown_minutes):
                        return
        
        # Find applicable policies
        for policy in self._remediation_policies.values():
            await self._execute_remediation_policy(service, policy, health_result)

    async def _execute_remediation_policy(
        self,
        service: str,
        policy: RemediationPolicy,
        health_result: HealthCheckResult
    ) -> None:
        """Execute remediation policy"""
        
        for action in policy.actions:
            await self._execute_remediation_action(service, action, policy.action_parameters)
        
        # Record remediation
        self._remediation_history.append({
            "service": service,
            "policy_id": policy.policy_id,
            "actions": [a.value for a in policy.actions],
            "timestamp": datetime.utcnow(),
            "trigger": health_result.message
        })
        
        self._last_remediation[service] = datetime.utcnow()

    async def _execute_remediation_action(
        self,
        service: str,
        action: RemediationAction,
        parameters: Dict[str, Any]
    ) -> bool:
        """Execute specific remediation action"""
        
        try:
            if action == RemediationAction.RESTART_SERVICE:
                await self._restart_service(service)
            
            elif action == RemediationAction.SCALE_UP:
                await self._scale_up_service(service, parameters)
            
            elif action == RemediationAction.CLEAR_CACHE:
                await self._clear_cache(service)
            
            elif action == RemediationAction.DATABASE_REPAIR:
                await self._repair_database(service)
            
            elif action == RemediationAction.CONNECTION_RESET:
                await self._reset_connections(service)
            
            elif action == RemediationAction.CIRCUIT_BREAKER_RESET:
                await self._reset_circuit_breaker(service)
            
            return True
        
        except Exception:
            return False

    # ========================================================================
    # Remediation Actions Implementation
    # ========================================================================

    async def _restart_service(self, service: str) -> bool:
        """Restart service"""
        print(f"[SELF-HEALING] Restarting service: {service}")
        self._health_status[service] = HealthStatus.RECOVERING
        # Implementation would trigger actual restart
        await asyncio.sleep(1)
        self._health_status[service] = HealthStatus.HEALTHY
        return True

    async def _scale_up_service(self, service: str, parameters: Dict[str, Any]) -> bool:
        """Scale up service"""
        replicas = parameters.get("replicas", 1)
        print(f"[SELF-HEALING] Scaling {service} to {replicas} replicas")
        # Implementation would trigger actual scaling
        return True

    async def _clear_cache(self, service: str) -> bool:
        """Clear service cache"""
        print(f"[SELF-HEALING] Clearing cache for {service}")
        # Implementation would clear actual cache
        return True

    async def _repair_database(self, service: str) -> bool:
        """Repair database"""
        print(f"[SELF-HEALING] Repairing database for {service}")
        # Implementation would run database repair
        return True

    async def _reset_connections(self, service: str) -> bool:
        """Reset connections for service"""
        print(f"[SELF-HEALING] Resetting connections for {service}")
        # Implementation would reset actual connections
        return True

    async def _reset_circuit_breaker(self, service: str) -> bool:
        """Reset circuit breaker"""
        if service in self._circuit_breakers:
            cb = self._circuit_breakers[service]
            cb.state = CircuitBreakerState.HALF_OPEN
            cb.failure_count = 0
            cb.success_count = 0
            print(f"[SELF-HEALING] Resetting circuit breaker for {service}")
            return True
        return False

    # ========================================================================
    # Circuit Breaker Pattern
    # ========================================================================

    def create_circuit_breaker(
        self,
        service_name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_sec: int = 60
    ) -> CircuitBreaker:
        """Create circuit breaker for service"""
        
        cb = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_sec=timeout_sec
        )
        
        self._circuit_breakers[service_name] = cb
        return cb

    def get_circuit_breaker_state(self, service_name: str) -> CircuitBreakerState:
        """Get current state of circuit breaker"""
        cb = self._circuit_breakers.get(service_name)
        
        if not cb:
            return CircuitBreakerState.CLOSED
        
        # Check for state transition to OPEN
        if cb.state == CircuitBreakerState.CLOSED:
            if cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitBreakerState.OPEN
                cb.last_state_change = datetime.utcnow()
        
        # Check for state transition from OPEN to HALF_OPEN (timeout)
        elif cb.state == CircuitBreakerState.OPEN:
            time_since_open = datetime.utcnow() - cb.last_state_change
            if time_since_open > timedelta(seconds=cb.timeout_sec):
                cb.state = CircuitBreakerState.HALF_OPEN
                cb.success_count = 0
                cb.last_state_change = datetime.utcnow()
        
        # Check for state transition from HALF_OPEN
        elif cb.state == CircuitBreakerState.HALF_OPEN:
            if cb.success_count >= cb.success_threshold:
                cb.state = CircuitBreakerState.CLOSED
                cb.failure_count = 0
                cb.last_state_change = datetime.utcnow()
            elif cb.failure_count >= 1:
                cb.state = CircuitBreakerState.OPEN
                cb.last_state_change = datetime.utcnow()
        
        return cb.state

    def record_success(self, service_name: str) -> None:
        """Record successful call"""
        if service_name in self._circuit_breakers:
            cb = self._circuit_breakers[service_name]
            cb.success_count += 1
            cb.failure_count = 0

    def record_failure(self, service_name: str) -> None:
        """Record failed call"""
        if service_name in self._circuit_breakers:
            cb = self._circuit_breakers[service_name]
            cb.failure_count += 1
            cb.success_count = 0

    # ========================================================================
    # Retry Logic with Exponential Backoff
    # ========================================================================

    async def retry_with_backoff(
        self,
        func: Callable,
        max_retries: int = 3,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 30.0,
        exponential_base: float = 2.0
    ) -> Any:
        """Execute function with exponential backoff retry"""
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    return func()
            
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay_sec * (exponential_base ** attempt),
                        max_delay_sec
                    )
                    # Add jitter (±10%)
                    jitter = delay * random.uniform(0.9, 1.1)
                    
                    await asyncio.sleep(jitter)
        
        raise last_exception

    # ========================================================================
    # Monitoring and Reporting
    # ========================================================================

    def get_service_health(self, service: str) -> Dict[str, Any]:
        """Get health status for service"""
        
        status = self._health_status.get(service, HealthStatus.HEALTHY)
        recent_checks = [
            r for r in self._health_history[-100:]
            if r.service == service
        ]
        
        return {
            "service": service,
            "status": status.value,
            "total_checks": len(recent_checks),
            "recent_failures": len([c for c in recent_checks if c.status != HealthStatus.HEALTHY]),
            "circuit_breaker_state": self._circuit_breakers.get(service, {}).get("state", "none")
        }

    def get_remediation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get remediation history"""
        return self._remediation_history[-limit:]

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_services": len(self._health_status),
            "healthy": len([s for s in self._health_status.values() if s == HealthStatus.HEALTHY]),
            "degraded": len([s for s in self._health_status.values() if s == HealthStatus.DEGRADED]),
            "unhealthy": len([s for s in self._health_status.values() if s == HealthStatus.UNHEALTHY]),
            "total_remediations": len(self._remediation_history)
        }
        
        return summary
