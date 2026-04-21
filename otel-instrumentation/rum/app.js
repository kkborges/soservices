/**
 * OpenTelemetry RUM (Real User Monitoring) para LAS
 * Monitora experiÃªncia do usuÃ¡rio no navegador
 * Auto-gerado pelo auto-instrumentador
 */

// ConfiguraÃ§Ã£o
// O token deve ser injetado pelo tenant/aplicacao, por exemplo via:
//   <meta name="las-rum-token" content="lsa_...">
// ou:
//   window.__LAS_RUM_TOKEN = "lsa_...";
const LAS_RUM_ENDPOINT = window.__LAS_RUM_ENDPOINT || 'https://api.soservices.com.br:8443/api/v1/ingest/rum';
const LAS_RUM_TOKEN = window.__LAS_RUM_TOKEN || (document.querySelector('meta[name=\"las-rum-token\"]')?.content || '');
const SERVICE_NAME = 'frontend-app';
const SAMPLE_RATE = 1.0;

/**
 * Inicializa a instrumentaÃ§Ã£o RUM
 */
async function initRUM() {
    // Carregar SDKs OTel para browser
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/@opentelemetry/auto-instrumentations-web@0.34.0/dist/auto-instrumentations-web.js';
    script.async = true;
    
    script.onload = () => {
        const { BasicTracerProvider, ConsoleSpanExporter, SimpleSpanProcessor } = window.otel;
        const { ZoneContextManager } = window.otel;
        
        // Criar provider
        const provider = new BasicTracerProvider({
            resource: new window.otel.Resource({
                attributes: {
                    'service.name': SERVICE_NAME,
                    'service.version': '1.0.0',
                    'rum.enabled': true,
                }
            })
        });
        
        // OTLP Exporter
        if (!LAS_RUM_TOKEN) {
            console.warn('[LAS RUM] Token ausente. Injete um token via meta tag ou window.__LAS_RUM_TOKEN.');
        }

        const exporter = new window.otel.OTLPTraceExporter({
            url: `${LAS_RUM_ENDPOINT}/v1/traces`,
            headers: LAS_RUM_TOKEN ? {
                'Authorization': `Bearer ${LAS_RUM_TOKEN}`,
                'Content-Type': 'application/json'
            } : { 'Content-Type': 'application/json' }
        });
        
        provider.addSpanProcessor(new SimpleSpanProcessor(exporter));
        provider.register();
        
        console.log('âœ“ RUM inicializado para LAS');
        
        // Rastrear navegaÃ§Ã£o
        trackPageNavigation();
        
        // Rastrear erros
        trackErrors();
        
        // Rastrear interaÃ§Ãµes do usuÃ¡rio
        trackUserInteractions();
    };
    
    document.head.appendChild(script);
}

/**
 * Rastreia navegaÃ§Ã£o entre pÃ¡ginas
 */
function trackPageNavigation() {
    const tracer = window.otel.trace.getTracer('page-navigation');
    
    // Performance Navigation Timing
    if (window.performance && window.performance.timing) {
        const perfData = window.performance.timing;
        const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
        
        tracer.startSpan('page-load', { attributes: {
            'page.url': window.location.href,
            'page.title': document.title,
            'navigation.time': pageLoadTime,
            'navigation.dom_interactive': perfData.domInteractive - perfData.navigationStart,
            'navigation.dom_complete': perfData.domComplete - perfData.navigationStart,
        }}).end();
    }
    
    // Single Page App navigation
    window.addEventListener('hashchange', () => {
        tracer.startSpan('page-navigation', { 
            attributes: {
                'page.url': window.location.href,
                'page.title': document.title,
            }
        }).end();
    });
}

/**
 * Rastreia erros JavaScript
 */
function trackErrors() {
    const tracer = window.otel.trace.getTracer('error-tracking');
    
    window.addEventListener('error', (event) => {
        tracer.startSpan('javascript-error', {
            attributes: {
                'error.message': event.message,
                'error.filename': event.filename,
                'error.lineno': event.lineno,
                'error.colno': event.colno,
                'severity': 'error',
            }
        }).recordException(new Error(event.message)).end();
    });
    
    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
        tracer.startSpan('unhandled-rejection', {
            attributes: {
                'error.message': event.reason?.toString?.() || 'Unknown rejection',
                'severity': 'error',
            }
        }).recordException(event.reason).end();
    });
}

/**
 * Rastreia interaÃ§Ãµes do usuÃ¡rio
 */
function trackUserInteractions() {
    const tracer = window.otel.trace.getTracer('user-interactions');
    
    // Cliques
    document.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A') {
            tracer.startSpan('user-click', {
                attributes: {
                    'element.type': e.target.tagName,
                    'element.id': e.target.id,
                    'element.class': e.target.className,
                    'element.text': e.target.textContent?.substring(0, 50),
                }
            }).end();
        }
    });
    
    // SubmissÃ£o de formulÃ¡rios
    document.addEventListener('submit', (e) => {
        tracer.startSpan('form-submit', {
            attributes: {
                'form.id': e.target.id,
                'form.name': e.target.name,
            }
        }).end();
    });
    
    // MudanÃ§as em inputs
    document.addEventListener('change', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
            tracer.startSpan('user-input-change', {
                attributes: {
                    'input.type': e.target.type,
                    'input.name': e.target.name,
                }
            }).end();
        }
    });
}

/**
 * API auxiliar para rastrear eventos customizados
 */
window.nexusRUM = {
    /**
     * Rastreia evento customizado
     * @param {string} eventName - Nome do evento
     * @param {object} attributes - Atributos adicionais
     */
    trackEvent(eventName, attributes = {}) {
        const tracer = window.otel?.trace?.getTracer('custom-events');
        if (tracer) {
            tracer.startSpan(eventName, { attributes }).end();
        }
    },
    
    /**
     * Rastreia operaÃ§Ã£o demorada
     * @param {string} operationName - Nome da operaÃ§Ã£o
     * @param {async function} fn - FunÃ§Ã£o a executar
     */
    async trackOperation(operationName, fn) {
        const tracer = window.otel?.trace?.getTracer('custom-operations');
        if (!tracer) return fn();
        
        const span = tracer.startSpan(operationName);
        try {
            const result = await fn();
            span.setStatus({ code: 0 });
            return result;
        } catch (error) {
            span.recordException(error);
            span.setStatus({ code: 2 });
            throw error;
        } finally {
            span.end();
        }
    },
    
    /**
     * Define atributo de usuÃ¡rio
     */
    setUserAttributes(userId, attributes = {}) {
        const tracer = window.otel?.trace?.getTracer('user-context');
        if (tracer) {
            const span = tracer.startSpan('set-user-context', {
                attributes: {
                    'user.id': userId,
                    ...attributes
                }
            });
            span.end();
        }
    }
};

// Iniciar RUM quando o documento estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRUM);
} else {
    initRUM();
}

