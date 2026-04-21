package com.las;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.concurrent.TimeUnit;

/**
 * Configuração do OpenTelemetry para LAS
 * Auto-gerado pelo auto-instrumentador
 */
@Configuration
public class OTelConfig {

    private static final String LAS_ENDPOINT = System.getenv()
        .getOrDefault("LAS_ENDPOINT", "http://api.soservices.com.br:8443");
    private static final String LAS_TOKEN = System.getenv().get("LAS_TOKEN");
    private static final String SERVICE_NAME = System.getenv()
        .getOrDefault("SERVICE_NAME", "java-service");
    private static final String SERVICE_ENV = System.getenv()
        .getOrDefault("SERVICE_ENVIRONMENT", "production");

    @Bean
    public OpenTelemetry openTelemetry() {
        Resource resource = Resource.getDefault()
            .merge(Resource.builder()
                .put(ResourceAttributes.SERVICE_NAME, SERVICE_NAME)
                .put(ResourceAttributes.SERVICE_VERSION, "1.0.0")
                .put(ResourceAttributes.DEPLOYMENT_ENVIRONMENT, SERVICE_ENV)
                .put("las.token", LAS_TOKEN != null ? LAS_TOKEN : "")
                .build());

        // OTLP Span Exporter
        OtlpGrpcSpanExporter.Builder exporterBuilder = OtlpGrpcSpanExporter.builder()
            .setEndpoint(LAS_ENDPOINT)
            .setTimeout(30, TimeUnit.SECONDS);
        if (LAS_TOKEN != null && !LAS_TOKEN.isBlank()) {
            exporterBuilder.addHeader("Authorization", "Bearer " + LAS_TOKEN);
        }
        OtlpGrpcSpanExporter otlpExporter = exporterBuilder.build();

        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .addSpanProcessor(BatchSpanProcessor.builder(otlpExporter).build())
            .setResource(resource)
            .build();

        OpenTelemetrySdk.getObservableMeterProvider();

        return OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .buildAndRegisterGlobal();
    }

    @Bean
    public Tracer tracer(OpenTelemetry openTelemetry) {
        return openTelemetry.getTracer(SERVICE_NAME);
    }
}
