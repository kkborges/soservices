/**
 * Exemplo: Express.js com OpenTelemetry e RUM
 */

// â† IMPORTANTE: Importar otel-init PRIMEIRO!
require('./otel-init.js');

const express = require('express');
const { trace } = require('@opentelemetry/api');

const app = express();
const tracer = trace.getTracer('express-example');

app.use(express.json());
app.use(express.static('public'));

// Middleware de tracing
app.use((req, res, next) => {
    const span = tracer.startSpan(`http.${req.method}`, {
        attributes: {
            'http.method': req.method,
            'http.url': req.url,
            'http.target': req.path,
        }
    });
    
    res.on('finish', () => {
        span.setStatus({ code: res.statusCode < 400 ? 0 : 2 });
        span.end();
    });
    
    next();
});

// Rotas
app.get('/', (req, res) => {
    res.send(`
        <html>
            <head>
                <title>Exemplo LAS</title>
                <style>
                    body { font-family: Arial; margin: 40px; }
                    button { padding: 10px; margin: 5px; }
                </style>
            </head>
            <body>
                <h1>Express.js com OpenTelemetry para LAS</h1>
                <h2>ðŸŽ¯ RUM ativado - Clique abaixo:</h2>
                
                <button onclick="trackClick()">Clique para rastrear</button>
                <button onclick="fetchTasks()">Buscar tasks</button>
                
                <h3>Resposta:</h3>
                <pre id="output"></pre>
                
                <script src="/app.js"></script>
                <script>
                    function trackClick() {
                        if (window.nexusRUM) {
                            nexusRUM.trackEvent('express-demo-click', {
                                'timestamp': new Date().toISOString()
                            });
                            alert('Evento rastreado!');
                        }
                    }
                    
                    async function fetchTasks() {
                        const resp = await fetch('/api/tasks');
                        const data = await resp.json();
                        document.getElementById('output').textContent = JSON.stringify(data, null, 2);
                    }
                </script>
            </body>
        </html>
    `);
});

app.get('/api/tasks', (req, res) => {
    const span = tracer.startSpan('fetch_tasks', {
        attributes: {
            'db.system': 'postgresql',
            'db.operation': 'SELECT'
        }
    });
    
    const tasks = [
        { id: 1, title: 'Task 1' },
        { id: 2, title: 'Task 2' }
    ];
    
    span.setStatus({ code: 0 });
    span.end();
    
    res.json({ tasks, count: tasks.length });
});

app.post('/api/tasks', (req, res) => {
    const span = tracer.startSpan('create_task', {
        attributes: {
            'task.title': req.body.title
        }
    });
    
    console.log('âœ“ Task criada:', req.body.title);
    
    span.end();
    res.json({ message: 'Task criada', task: req.body });
});

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
    console.log(`âœ“ Servidor rodando em http://localhost:${PORT}`);
    console.log(`  Traces sendo enviados para LAS`);
});

