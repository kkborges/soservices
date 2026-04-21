"""
Exemplo: AplicaÃ§Ã£o FastAPI com OpenTelemetry e RUM
"""

import otel_init  # â† IMPORTANTE: Importar primeiro!

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from opentelemetry import trace
import psycopg2

app = FastAPI(title="Exemplo LAS")
tracer = trace.get_tracer(__name__)

# Servir app.js para RUM
app.mount("/public", StaticFiles(directory="public"), name="public")

class Task(BaseModel):
    id: int
    title: str

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head>
            <title>Exemplo LAS</title>
            <style>
                body { font-family: Arial; margin: 40px; }
                button { padding: 10px; margin: 5px; }
            </style>
        </head>
        <body>
            <h1>AplicaÃ§Ã£o com OpenTelemetry para LAS</h1>
            <h2>ðŸŽ¯ RUM ativado - Clique abaixo para rastrear:</h2>
            
            <button onclick="trackClick()" id="btn1">Clique para rastrear</button>
            <button onclick="fetchData()" id="btn2">Buscar dados</button>
            
            <h3>Dados:</h3>
            <pre id="output"></pre>
            
            <script src="/public/app.js"></script>
            <script>
                function trackClick() {
                    if (window.nexusRUM) {
                        nexusRUM.trackEvent('demo-button-clicked', {
                            'button.id': 'btn1',
                            'timestamp': new Date().toISOString()
                        });
                        alert('Evento rastreado! Verifique no LAS');
                    }
                }
                
                async function fetchData() {
                    try {
                        const resp = await fetch('/api/tasks');
                        const data = await resp.json();
                        document.getElementById('output').textContent = JSON.stringify(data, null, 2);
                    } catch (e) {
                        alert('Erro: ' + e.message);
                    }
                }
            </script>
        </body>
    </html>
    """

@app.get("/api/tasks")
async def get_tasks():
    """Endpoint rastreado com OpenTelemetry"""
    with tracer.start_as_current_span("fetch_tasks") as span:
        try:
            # Simular conexÃ£o DB
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.operation", "SELECT")
            
            tasks = [
                {"id": 1, "title": "Task 1"},
                {"id": 2, "title": "Task 2"}
            ]
            
            span.set_attribute("db.rows_returned", len(tasks))
            return {"tasks": tasks, "count": len(tasks)}
            
        except Exception as e:
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks")
async def create_task(task: Task):
    """Criar nova task - Rastreado"""
    with tracer.start_as_current_span("create_task") as span:
        span.set_attribute("task.id", task.id)
        span.set_attribute("task.title", task.title)
        
        print(f"âœ“ Task criada: {task.title}")
        return {"message": "Task criada", "task": task}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

