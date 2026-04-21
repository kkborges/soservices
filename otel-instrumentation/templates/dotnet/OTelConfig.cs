using OpenTelemetry;
using OpenTelemetry.Exporter;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using OpenTelemetry.Metrics;
using System;
using Microsoft.Extensions.DependencyInjection;

namespace LAS.Instrumentation
{
    /// <summary>
    /// Configuração do OpenTelemetry para LAS
    /// Auto-gerado pelo auto-instrumentador
    /// </summary>
    public static class OTelConfig
    {
        private static readonly string LasEndpoint = 
            Environment.GetEnvironmentVariable("LAS_ENDPOINT") ?? 
            "https://api.soservices.com.br:8443/api/v1/ingest/otel";
        
        private static readonly string LasToken = 
            Environment.GetEnvironmentVariable("LAS_TOKEN");
        
        private static readonly string ServiceName = 
            Environment.GetEnvironmentVariable("SERVICE_NAME") ?? "dotnet-service";
        
        private static readonly string ServiceEnvironment = 
            Environment.GetEnvironmentVariable("SERVICE_ENVIRONMENT") ?? "production";

        public static IServiceCollection AddLasOpenTelemetry(this IServiceCollection services)
        {
            var resource = ResourceBuilder.CreateDefault()
                .AddService(ServiceName, serviceVersion: "1.0.0")
                .AddAttributes(new Dictionary<string, object>
                {
                    { "deployment.environment", ServiceEnvironment },
                    { "las.token", LasToken ?? "" }
                });

            services.AddOpenTelemetry()
                .WithTracing(tracerProvider =>
                {
                    tracerProvider
                        .SetResourceBuilder(resource)
                        .AddAspNetCoreInstrumentation()
                        .AddHttpClientInstrumentation()
                        .AddSqlClientInstrumentation()
                        .AddOtlpExporter(options =>
                        {
                            options.Endpoint = new Uri(LasEndpoint);
                            if (!string.IsNullOrEmpty(LasToken))
                            {
                                options.Headers = $"Authorization: Bearer {LasToken}";
                            }
                        });
                })
                .WithMetrics(metricsProvider =>
                {
                    metricsProvider
                        .SetResourceBuilder(resource)
                        .AddAspNetCoreInstrumentation()
                        .AddHttpClientInstrumentation()
                        .AddOtlpExporter(options =>
                        {
                            options.Endpoint = new Uri(LasEndpoint);
                        });
                });

            Console.WriteLine($"✓ OpenTelemetry inicializado para {ServiceName}");
            Console.WriteLine($"  Endpoint: {LasEndpoint}");

            return services;
        }
    }
}
