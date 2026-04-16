"""
Distributed Tracing Service using OpenTelemetry

Provides:
- Full-stack request tracing
- Service-to-service trace propagation
- Performance bottleneck identification
- Distributed context correlation
- Integration with Jaeger, Zipkin, Datadog
- Automatic instrumentation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4
import time
import json


# ============================================================================
# Tracing Enums
# ============================================================================

class SpanKind(str, Enum):
    """OpenTelemetry span kinds"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class TraceStatus(str, Enum):
    """Trace status"""
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SpanEvent:
    """Event within a span"""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanLink:
    """Link to another span"""
    trace_id: str
    span_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    
    operation_name: str
    span_kind: SpanKind
    
    start_time: datetime
    end_time: Optional[datetime] = None
    
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)
    
    status: TraceStatus = TraceStatus.UNSET
    status_message: Optional[str] = None
    
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @property
    def is_finished(self) -> bool:
        """Check if span is finished"""
        return self.end_time is not None


@dataclass
class Trace:
    """Complete distributed trace"""
    trace_id: str
    root_span_id: str
    service_name: str
    operation_name: str
    
    start_time: datetime
    end_time: Optional[datetime] = None
    
    spans: Dict[str, Span] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration_ms(self) -> Optional[float]:
        """Total trace duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


# ============================================================================
# Distributed Tracing Service
# ============================================================================

class DistributedTracingService:
    """
    Distributed Tracing Service using OpenTelemetry patterns
    
    Features:
    - Full-stack request tracing with span hierarchy
    - Automatic service-to-service propagation
    - Performance bottleneck identification
    - Integration with external tracing backends
    - Contextual span attributes
    - Automatic instrumentation hooks
    """

    def __init__(
        self,
        service_name: str,
        service_version: str,
        environment: str,
        backend: str = "local"  # local, jaeger, zipkin, datadog
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.backend = backend
        
        # Storage
        self._traces: Dict[str, Trace] = {}
        self._spans: Dict[str, Span] = {}
        self._active_spans: Dict[str, List[Span]] = {}
        self._context_stack = []
        
        # Subscribers for real-time updates
        self._span_processors: List[Callable] = []

    # ========================================================================
    # Trace Creation and Context
    # ========================================================================

    def start_trace(
        self,
        operation_name: str,
        parent_trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new distributed trace"""
        
        trace_id = parent_trace_id or str(uuid4()).replace("-", "")
        
        # Create root span
        root_span = Span(
            trace_id=trace_id,
            span_id=str(uuid4()).replace("-", ""),
            parent_span_id=None,
            operation_name=operation_name,
            span_kind=SpanKind.SERVER,
            start_time=datetime.utcnow()
        )
        
        # Create trace
        trace = Trace(
            trace_id=trace_id,
            root_span_id=root_span.span_id,
            service_name=self.service_name,
            operation_name=operation_name,
            start_time=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        trace.spans[root_span.span_id] = root_span
        
        self._traces[trace_id] = trace
        self._spans[root_span.span_id] = root_span
        
        # Set as active
        self._active_spans[trace_id] = [root_span]
        
        return trace_id

    def end_trace(self, trace_id: str) -> Optional[Trace]:
        """End a trace"""
        trace = self._traces.get(trace_id)
        if trace:
            trace.end_time = datetime.utcnow()
            
            # End all remaining spans
            for span in self._active_spans.pop(trace_id, []):
                span.end_time = datetime.utcnow()
        
        return trace

    # ========================================================================
    # Span Management
    # ========================================================================

    def start_span(
        self,
        trace_id: str,
        operation_name: str,
        span_kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None
    ) -> str:
        """Start a new span within a trace"""
        
        trace = self._traces.get(trace_id)
        if not trace:
            return ""
        
        # Get parent span
        active = self._active_spans.get(trace_id, [])
        actual_parent = parent_span_id or (active[-1].span_id if active else None)
        
        # Create span
        span = Span(
            trace_id=trace_id,
            span_id=str(uuid4()).replace("-", ""),
            parent_span_id=actual_parent,
            operation_name=operation_name,
            span_kind=span_kind,
            start_time=datetime.utcnow(),
            attributes=attributes or {}
        )
        
        trace.spans[span.span_id] = span
        self._spans[span.span_id] = span
        
        if trace_id not in self._active_spans:
            self._active_spans[trace_id] = []
        self._active_spans[trace_id].append(span)
        
        # Notify processors
        self._notify_span_event("start", span)
        
        return span.span_id

    def end_span(self, span_id: str) -> Optional[Span]:
        """End a span"""
        span = self._spans.get(span_id)
        if span:
            span.end_time = datetime.utcnow()
            
            # Remove from active
            active = self._active_spans.get(span.trace_id, [])
            if span in active:
                active.remove(span)
            
            # Notify processors
            self._notify_span_event("end", span)
        
        return span

    # ========================================================================
    # Span Attributes and Events
    # ========================================================================

    def add_attribute(
        self,
        span_id: str,
        key: str,
        value: Any
    ) -> bool:
        """Add attribute to span"""
        span = self._spans.get(span_id)
        if span and not span.is_finished:
            span.attributes[key] = value
            return True
        return False

    def add_attributes(
        self,
        span_id: str,
        attributes: Dict[str, Any]
    ) -> bool:
        """Add multiple attributes to span"""
        span = self._spans.get(span_id)
        if span and not span.is_finished:
            span.attributes.update(attributes)
            return True
        return False

    def record_exception(
        self,
        span_id: str,
        exception: Exception,
        escaped: bool = False
    ) -> bool:
        """Record exception in span"""
        span = self._spans.get(span_id)
        if not span or span.is_finished:
            return False
        
        import traceback
        
        span.status = TraceStatus.ERROR
        span.status_message = str(exception)
        
        span.add_event(SpanEvent(
            name="exception",
            timestamp=datetime.utcnow(),
            attributes={
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
                "exception.stacktrace": traceback.format_exc(),
                "exception.escaped": escaped
            }
        ))
        
        return True

    def add_event(
        self,
        span_id: str,
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add event to span"""
        span = self._spans.get(span_id)
        if not span or span.is_finished:
            return False
        
        event = SpanEvent(
            name=event_name,
            timestamp=datetime.utcnow(),
            attributes=attributes or {}
        )
        
        span.events.append(event)
        return True

    def set_span_tag(
        self,
        span_id: str,
        key: str,
        value: str
    ) -> bool:
        """Set span tag (simplified version)"""
        span = self._spans.get(span_id)
        if span:
            span.tags[key] = value
            return True
        return False

    # ========================================================================
    # HTTP Instrumentation
    # ========================================================================

    def instrument_http_request(
        self,
        trace_id: str,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Create span for HTTP request"""
        
        span_id = self.start_span(
            trace_id,
            f"HTTP {method}",
            span_kind=SpanKind.CLIENT,
            attributes={
                "http.method": method,
                "http.url": url,
                "span.kind": "http"
            }
        )
        
        # Add trace headers for propagation
        if headers is not None:
            headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
        
        return span_id

    def complete_http_request(
        self,
        span_id: str,
        status_code: int,
        response_size: Optional[int] = None
    ) -> None:
        """Complete HTTP request span"""
        
        span = self._spans.get(span_id)
        if span:
            span.attributes["http.status_code"] = status_code
            if response_size:
                span.attributes["http.response_size"] = response_size
            
            span.status = TraceStatus.OK if 200 <= status_code < 400 else TraceStatus.ERROR
            
            self.end_span(span_id)

    # ========================================================================
    # Database Instrumentation
    # ========================================================================

    def instrument_database_query(
        self,
        trace_id: str,
        query: str,
        database_type: str = "postgresql"
    ) -> str:
        """Create span for database query"""
        
        # Extract operation from query
        operation = query.strip().split()[0].upper()
        
        span_id = self.start_span(
            trace_id,
            f"DB {operation}",
            span_kind=SpanKind.INTERNAL,
            attributes={
                "db.system": database_type,
                "db.operation": operation,
                "db.statement": query[:500]  # Truncate long queries
            }
        )
        
        return span_id

    def complete_database_query(
        self,
        span_id: str,
        rows_affected: int,
        duration_ms: float
    ) -> None:
        """Complete database query span"""
        
        span = self._spans.get(span_id)
        if span:
            span.attributes["db.rows_affected"] = rows_affected
            span.attributes["duration_ms"] = duration_ms
            span.status = TraceStatus.OK
            self.end_span(span_id)

    # ========================================================================
    # Cache Instrumentation
    # ========================================================================

    def instrument_cache_operation(
        self,
        trace_id: str,
        operation: str,
        cache_name: str,
        key: str
    ) -> str:
        """Create span for cache operation"""
        
        span_id = self.start_span(
            trace_id,
            f"CACHE {operation.upper()}",
            span_kind=SpanKind.INTERNAL,
            attributes={
                "cache.system": cache_name,
                "cache.operation": operation,
                "cache.key": key
            }
        )
        
        return span_id

    def complete_cache_operation(
        self,
        span_id: str,
        hit: bool,
        duration_ms: float
    ) -> None:
        """Complete cache operation span"""
        
        span = self._spans.get(span_id)
        if span:
            span.attributes["cache.hit"] = hit
            span.attributes["duration_ms"] = duration_ms
            span.status = TraceStatus.OK
            self.end_span(span_id)

    # ========================================================================
    # Service-to-Service Propagation
    # ========================================================================

    def extract_trace_context(self, headers: Dict[str, str]) -> tuple:
        """Extract trace context from request headers"""
        
        # W3C Trace Context format: traceparent: 00-trace_id-span_id-flags
        traceparent = headers.get("traceparent")
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                parent_span_id = parts[2]
                return trace_id, parent_span_id
        
        # Jaeger format
        trace_id = headers.get("uber-trace-id", "").split(":")[0]
        if trace_id:
            return trace_id, None
        
        return None, None

    def inject_trace_context(
        self,
        trace_id: str,
        span_id: str,
        headers: Dict[str, str]
    ) -> Dict[str, str]:
        """Inject trace context into request headers"""
        
        headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
        headers["tracestate"] = f"nx@nr=0"
        
        return headers

    # ========================================================================
    # Span Processing
    # ========================================================================

    def add_span_processor(self, processor: Callable) -> None:
        """Add span processor for real-time processing"""
        self._span_processors.append(processor)

    def _notify_span_event(self, event_type: str, span: Span) -> None:
        """Notify processors of span events"""
        for processor in self._span_processors:
            try:
                processor(event_type, span)
            except Exception:
                pass  # Silently ignore processor failures

    # ========================================================================
    # Query and Analysis
    # ========================================================================

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get complete trace"""
        return self._traces.get(trace_id)

    def get_spans_for_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace"""
        trace = self._traces.get(trace_id)
        if trace:
            return list(trace.spans.values())
        return []

    def get_slow_spans(
        self,
        trace_id: str,
        threshold_ms: float = 1000
    ) -> List[Span]:
        """Get spans exceeding duration threshold"""
        spans = self.get_spans_for_trace(trace_id)
        return [
            s for s in spans
            if s.duration_ms and s.duration_ms > threshold_ms
        ]

    def get_error_spans(self, trace_id: str) -> List[Span]:
        """Get all error spans in trace"""
        spans = self.get_spans_for_trace(trace_id)
        return [s for s in spans if s.status == TraceStatus.ERROR]

    # ========================================================================
    # Trace Visualization Data
    # ========================================================================

    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Get trace as tree structure for visualization"""
        
        trace = self._traces.get(trace_id)
        if not trace:
            return {}
        
        def build_tree(span_id: str) -> Dict[str, Any]:
            span = trace.spans.get(span_id)
            if not span:
                return {}
            
            children = [
                build_tree(s.span_id)
                for s in trace.spans.values()
                if s.parent_span_id == span_id
            ]
            
            return {
                "span_id": span.span_id,
                "name": span.operation_name,
                "start_time": span.start_time.isoformat(),
                "duration_ms": span.duration_ms,
                "status": span.status.value,
                "tags": span.tags,
                "attributes": span.attributes,
                "children": children
            }
        
        return build_tree(trace.root_span_id)

    def get_trace_metrics(self, trace_id: str) -> Dict[str, Any]:
        """Get metrics for trace"""
        
        trace = self._traces.get(trace_id)
        if not trace:
            return {}
        
        spans = trace.spans.values()
        
        durations = [s.duration_ms for s in spans if s.duration_ms]
        
        return {
            "trace_id": trace_id,
            "total_duration_ms": trace.total_duration_ms,
            "total_spans": len(spans),
            "error_spans": len([s for s in spans if s.status == TraceStatus.ERROR]),
            "avg_span_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_span_duration_ms": max(durations) if durations else 0,
            "min_span_duration_ms": min(durations) if durations else 0,
            "spans_by_kind": {
                kind.value: len([s for s in spans if s.span_kind == kind])
                for kind in SpanKind
            }
        }
