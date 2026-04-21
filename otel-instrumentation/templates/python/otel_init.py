"""
Inicialização do OpenTelemetry para LAS
Auto-gerado pelo auto-instrumentador
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import ssl

# Configuração do LAS
LAS_ENDPOINT = os.getenv('LAS_ENDPOINT', 'https://api.soservices.com.br:8443/api/v1/ingest/otel')
LAS_TOKEN = os.getenv('LAS_TOKEN')
SERVICE_NAME = os.getenv('SERVICE_NAME', 'python-service')
SERVICE_ENVIRONMENT = os.getenv('SERVICE_ENVIRONMENT', 'production')

def init_otel():
    """Inicializa OpenTelemetry com LAS"""
    
    # Resource
    resource = Resource(attributes={
        "service.name": SERVICE_NAME,
        "service.environment": SERVICE_ENVIRONMENT,
        "service.version": "1.0.0",
        "las.token": LAS_TOKEN,
    })
    
    # Tracer Provider
    tracer_provider = TracerProvider(resource=resource)
    
    # OTLP Exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=LAS_ENDPOINT,
        headers={"Authorization": f"Bearer {LAS_TOKEN}"} if LAS_TOKEN else {},
    )
    
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)
    
    # Metrics (opcional)
    if os.getenv('ENABLE_METRICS', 'true').lower() == 'true':
        metric_exporter = OTLPMetricExporter(
            endpoint=LAS_ENDPOINT,
            headers={"Authorization": f"Bearer {LAS_TOKEN}"} if LAS_TOKEN else {},
        )
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
    
    # Auto-instrumentação
    FastAPIInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    print(f"✓ OpenTelemetry inicializado para {SERVICE_NAME}")
    print(f"  Endpoint: {LAS_ENDPOINT}")

if __name__ == 'otel_init':
    init_otel()
