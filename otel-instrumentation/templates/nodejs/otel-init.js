/**
 * Inicialização do OpenTelemetry para LAS
 * DEVE ser importado ANTES de qualquer outro módulo
 * Auto-gerado pelo auto-instrumentador
 */

require('dotenv').config();

const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const { ConsoleSpanExporter } = require('@opentelemetry/sdk-trace-node');

const lasEndpoint = process.env.LAS_ENDPOINT || 'https://api.soservices.com.br:8443/api/v1/ingest/otel';
const lasToken = process.env.LAS_TOKEN;
const serviceName = process.env.SERVICE_NAME || 'nodejs-service';
const serviceEnvironment = process.env.SERVICE_ENVIRONMENT || 'production';
const debugMode = process.env.DEBUG_MODE === 'true';

// Configurar OTLP Exporter
const otlpExporter = new OTLPTraceExporter({
    url: lasEndpoint,
    headers: lasToken ? { 'Authorization': `Bearer ${lasToken}` } : {},
});

// Inicializar SDK
const sdk = new NodeSDK({
    resource: {
        attributes: {
            'service.name': serviceName,
            'service.environment': serviceEnvironment,
            'service.version': '1.0.0',
            'las.token': lasToken,
        },
    },
    traceExporter: debugMode ? new ConsoleSpanExporter() : otlpExporter,
    instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();

console.log(`✓ OpenTelemetry inicializado para ${serviceName}`);
console.log(`  Endpoint: ${lasEndpoint}`);

// Graceful shutdown
process.on('SIGTERM', () => {
    sdk.shutdown()
        .then(() => console.log('✓ OpenTelemetry finalizado'))
        .catch((err) => console.error('Erro ao finalizar OpenTelemetry:', err));
});

module.exports = sdk;
