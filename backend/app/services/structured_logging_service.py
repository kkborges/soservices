"""
Enterprise Structured Logging Service

Provides:
- JSON-formatted structured logs
- Log levels with context
- Integration with log aggregation systems (ELK, Datadog, etc.)
- Contextual logging with correlation IDs
- Performance metrics logging
- Centralized log storage and querying
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import uuid4
from pythonjsonlogger import jsonlogger
import time


# ============================================================================
# Logging Enums
# ============================================================================

class LogLevel(str, Enum):
    """Log severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log categories for organization"""
    APPLICATION = "application"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATABASE = "database"
    API = "api"
    INTEGRATION = "integration"
    AUDIT = "audit"
    MONITORING = "monitoring"
    ERROR = "error"


# ============================================================================
# Structured Log Entry
# ============================================================================

@dataclass
class StructuredLogEntry:
    """Structured log entry with metadata"""
    timestamp: str
    level: str
    category: str
    message: str
    
    # Correlation
    correlation_id: str
    request_id: str
    trace_id: str
    
    # Context
    service_name: str
    service_version: str
    environment: str
    
    # User/Tenant context
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Request context
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    
    # Performance metrics
    db_queries: Optional[int] = None
    cache_hits: Optional[int] = None
    cache_misses: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    
    # Error information
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Additional context
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        if data.get("metadata") is None:
            del data["metadata"]
        return data

    def to_json(self) -> str:
        """Convert to JSON string"""
        data = self.to_dict()
        return json.dumps(data)


# ============================================================================
# Structured Logging Service
# ============================================================================

class StructuredLoggingService:
    """
    Enterprise Structured Logging Service
    
    Features:
    - Structured JSON logging for all log entries
    - Correlation ID tracking across requests
    - Contextual logging with request/user information
    - Performance metrics and timing information
    - Integration with centralized logging systems
    - Log filtering and sampling
    - Error tracking with stack traces
    """

    def __init__(
        self,
        service_name: str,
        service_version: str,
        environment: str,
        min_level: LogLevel = LogLevel.INFO
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.min_level = min_level
        
        # Context storage (thread-local in production)
        self._context: Dict[str, Any] = {}
        self._log_entries: List[StructuredLogEntry] = []
        
        # Setup logger
        self.logger = self._setup_logger()

    # ========================================================================
    # Logger Setup
    # ========================================================================

    def _setup_logger(self) -> logging.Logger:
        """Setup JSON logger"""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(logging.DEBUG)
        
        # JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger

    # ========================================================================
    # Context Management
    # ========================================================================

    def set_correlation_id(self, correlation_id: Optional[str] = None) -> str:
        """Set correlation ID for request tracking"""
        correlation_id = correlation_id or str(uuid4())
        self._context["correlation_id"] = correlation_id
        return correlation_id

    def get_correlation_id(self) -> str:
        """Get current correlation ID"""
        return self._context.get("correlation_id", str(uuid4()))

    def set_request_context(
        self,
        request_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """Set request context"""
        self._context.update({
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "trace_id": str(uuid4())
        })

    def set_user_context(self, user_id: str, tenant_id: str) -> None:
        """Set user context"""
        self._context["user_id"] = user_id
        self._context["tenant_id"] = tenant_id

    def get_context(self) -> Dict[str, Any]:
        """Get current context"""
        return self._context.copy()

    def clear_context(self) -> None:
        """Clear context"""
        self._context.clear()

    # ========================================================================
    # Logging Methods
    # ========================================================================

    def _create_log_entry(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> StructuredLogEntry:
        """Create structured log entry"""
        
        # Extract request_id from kwargs if present to avoid duplicate argument
        request_id = kwargs.pop("request_id", self._context.get("request_id", ""))
        
        entry = StructuredLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level.value,
            category=category.value,
            message=message,
            correlation_id=self._context.get("correlation_id", str(uuid4())),
            request_id=request_id,
            trace_id=self._context.get("trace_id", str(uuid4())),
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            tenant_id=self._context.get("tenant_id"),
            user_id=self._context.get("user_id"),
            session_id=self._context.get("session_id"),
            **kwargs
        )
        
        return entry

    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        """Log message with structured context"""
        
        entry = self._create_log_entry(level, category, message, **kwargs)
        self._log_entries.append(entry)
        
        # Output to logger
        log_dict = entry.to_dict()
        log_dict["message"] = message  # Ensure message is included
        
        python_level = getattr(logging, level.value)
        self.logger.log(python_level, json.dumps(log_dict))

    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        **kwargs
    ) -> None:
        """Log debug message"""
        self.log(LogLevel.DEBUG, category, message, **kwargs)

    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        **kwargs
    ) -> None:
        """Log info message"""
        self.log(LogLevel.INFO, category, message, **kwargs)

    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        **kwargs
    ) -> None:
        """Log warning message"""
        self.log(LogLevel.WARNING, category, message, **kwargs)

    def error(
        self,
        message: str,
        category: LogCategory = LogCategory.ERROR,
        error_code: Optional[str] = None,
        error_type: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log error message"""
        self.log(
            LogLevel.ERROR,
            category,
            message,
            error_code=error_code,
            error_type=error_type,
            error_message=message,
            stack_trace=stack_trace,
            **kwargs
        )

    def critical(
        self,
        message: str,
        category: LogCategory = LogCategory.ERROR,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log critical message"""
        self.log(
            LogLevel.CRITICAL,
            category,
            message,
            error_code=error_code,
            **kwargs
        )

    # ========================================================================
    # API Logging
    # ========================================================================

    def log_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, str]] = None
    ) -> str:
        """Log incoming request"""
        request_id = str(uuid4())
        
        # Add query_params to metadata if present
        metadata = {"query_params": query_params} if query_params else None
        
        self.log(
            LogLevel.INFO,
            LogCategory.API,
            f"Incoming request: {method} {path}",
            request_id=request_id,
            method=method,
            path=path,
            metadata=metadata
        )
        
        self._context["request_id"] = request_id
        return request_id

    def log_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        db_queries: Optional[int] = None,
        **kwargs
    ) -> None:
        """Log response"""
        
        level = LogLevel.INFO if 200 <= status_code < 400 else LogLevel.WARNING
        
        self.log(
            level,
            LogCategory.API,
            f"Response: {method} {path} -> {status_code}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            db_queries=db_queries,
            **kwargs
        )

    # ========================================================================
    # Performance Logging
    # ========================================================================

    def log_database_query(
        self,
        query: str,
        duration_ms: float,
        rows_affected: int
    ) -> None:
        """Log database query"""
        
        level = LogLevel.WARNING if duration_ms > 1000 else LogLevel.DEBUG
        
        self.log(
            level,
            LogCategory.DATABASE,
            f"Database query executed in {duration_ms:.2f}ms",
            query_preview=query[:200],  # First 200 chars
            duration_ms=duration_ms,
            rows_affected=rows_affected
        )

    def log_cache_hit(
        self,
        cache_key: str,
        hit: bool
    ) -> None:
        """Log cache hit/miss"""
        
        self.log(
            LogLevel.DEBUG,
            LogCategory.PERFORMANCE,
            f"Cache {'hit' if hit else 'miss'}: {cache_key}",
            cache_key=cache_key,
            cache_hit=hit
        )

    def log_external_api_call(
        self,
        api_name: str,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """Log external API call"""
        
        level = LogLevel.WARNING if status_code >= 400 else LogLevel.INFO
        
        self.log(
            level,
            LogCategory.INTEGRATION,
            f"External API call to {api_name}: {method} {endpoint}",
            api_name=api_name,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms
        )

    # ========================================================================
    # Security Logging
    # ========================================================================

    def log_authentication_attempt(
        self,
        user_id: str,
        success: bool,
        method: str,
        failure_reason: Optional[str] = None
    ) -> None:
        """Log authentication attempt"""
        
        level = LogLevel.INFO if success else LogLevel.WARNING
        
        self.log(
            level,
            LogCategory.SECURITY,
            f"Authentication {'successful' if success else 'failed'}: {user_id}",
            user_id=user_id,
            auth_method=method,
            auth_success=success,
            failure_reason=failure_reason
        )

    def log_authorization_check(
        self,
        user_id: str,
        resource: str,
        action: str,
        allowed: bool
    ) -> None:
        """Log authorization check"""
        
        level = LogLevel.INFO if allowed else LogLevel.WARNING
        
        self.log(
            level,
            LogCategory.SECURITY,
            f"Authorization {'granted' if allowed else 'denied'}: {user_id} -> {resource}:{action}",
            user_id=user_id,
            resource=resource,
            action=action,
            auth_allowed=allowed
        )

    def log_suspicious_activity(
        self,
        activity_type: str,
        description: str,
        severity: str = "medium"
    ) -> None:
        """Log suspicious activity"""
        
        level = (
            LogLevel.CRITICAL if severity == "high" else
            LogLevel.WARNING if severity == "medium" else
            LogLevel.INFO
        )
        
        self.log(
            level,
            LogCategory.SECURITY,
            f"Suspicious activity detected: {activity_type}",
            activity_type=activity_type,
            description=description,
            severity=severity
        )

    # ========================================================================
    # Error Logging
    # ========================================================================

    def log_exception(
        self,
        exception: Exception,
        message: Optional[str] = None,
        category: LogCategory = LogCategory.ERROR
    ) -> None:
        """Log exception with stack trace"""
        
        import traceback
        
        self.log(
            LogLevel.ERROR,
            category,
            message or str(exception),
            error_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=traceback.format_exc()
        )

    # ========================================================================
    # Metrics Logging
    # ========================================================================

    def log_metrics(
        self,
        duration_ms: float,
        db_queries: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
        memory_usage_mb: Optional[float] = None
    ) -> None:
        """Log performance metrics"""
        
        self.log(
            LogLevel.DEBUG,
            LogCategory.PERFORMANCE,
            "Performance metrics",
            duration_ms=duration_ms,
            db_queries=db_queries,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            memory_usage_mb=memory_usage_mb
        )

    # ========================================================================
    # Query and Retrieval
    # ========================================================================

    def get_logs(
        self,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent logs"""
        
        logs = self._log_entries
        
        if level:
            logs = [l for l in logs if l.level == level.value]
        
        if category:
            logs = [l for l in logs if l.category == category.value]
        
        return [l.to_dict() for l in logs[-limit:]]

    def get_logs_by_correlation_id(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all logs for correlation ID"""
        logs = [
            l for l in self._log_entries
            if l.correlation_id == correlation_id
        ]
        return [l.to_dict() for l in logs]

    def get_logs_by_request_id(self, request_id: str) -> List[Dict[str, Any]]:
        """Get all logs for request"""
        logs = [
            l for l in self._log_entries
            if l.request_id == request_id
        ]
        return [l.to_dict() for l in logs]

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        
        by_level = {}
        by_category = {}
        
        for entry in self._log_entries:
            by_level[entry.level] = by_level.get(entry.level, 0) + 1
            by_category[entry.category] = by_category.get(entry.category, 0) + 1
        
        return {
            "total_entries": len(self._log_entries),
            "by_level": by_level,
            "by_category": by_category,
            "unique_correlation_ids": len(set(e.correlation_id for e in self._log_entries)),
            "unique_request_ids": len(set(e.request_id for e in self._log_entries if e.request_id))
        }

    # ========================================================================
    # Export
    # ========================================================================

    def export_logs(self) -> str:
        """Export all logs as JSONL"""
        lines = [entry.to_json() for entry in self._log_entries]
        return "\n".join(lines)
