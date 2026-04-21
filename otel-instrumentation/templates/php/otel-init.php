<?php
/**
 * Inicialização do OpenTelemetry para LAS
 * Auto-gerado pelo auto-instrumentador
 */

require_once __DIR__ . '/vendor/autoload.php';

use OpenTelemetry\API\Trace\TracerInterface;
use OpenTelemetry\SDK\Trace\TracerProvider;
use OpenTelemetry\SDK\Trace\SpanProcessor\BatchSpanProcessor;
use OpenTelemetry\Exporter\OTLP\OTLPExporterFactory;
use OpenTelemetry\SDK\Resource\ResourceInfo;
use OpenTelemetry\SemConv\ResourceAttributes;

// Configuração LAS
$lasEndpoint = $_ENV['LAS_ENDPOINT'] ?? 'https://api.soservices.com.br:8443/api/v1/ingest/otel';
$lasToken = $_ENV['LAS_TOKEN'] ?? null;
$serviceName = $_ENV['SERVICE_NAME'] ?? 'php-service';
$serviceEnvironment = $_ENV['SERVICE_ENVIRONMENT'] ?? 'production';

// Resource
$resource = ResourceInfo::create([
    ResourceAttributes::SERVICE_NAME => $serviceName,
    ResourceAttributes::SERVICE_VERSION => '1.0.0',
    ResourceAttributes::DEPLOYMENT_ENVIRONMENT => $serviceEnvironment,
    'las.token' => $lasToken ?? '',
]);

// OTLP Exporter
$exporter = (new OTLPExporterFactory())->create();

// Tracer Provider
$tracerProvider = new TracerProvider(
    null,
    new BatchSpanProcessor($exporter),
    null,
    $resource
);

// Tracer
$tracer = $tracerProvider->getTracer('php-service');

echo "✓ OpenTelemetry inicializado para {$serviceName}\n";
echo "  Endpoint: {$lasEndpoint}\n";

return [
    'tracer' => $tracer,
    'provider' => $tracerProvider,
];
?>
