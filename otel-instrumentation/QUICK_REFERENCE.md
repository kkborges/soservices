# âš¡ QUICK REFERENCE - Guia RÃ¡pido Visual

## ðŸŽ¯ ComeÃ§ar em 30 Segundos

```bash
# 1. Menu interativo (MAIS FÃCIL)
python otel-instrumentation/guide.py

# OU

# 2. Script direto
cd seu-projeto
python otel-instrumentation/instrument.py .

# OU

# 3. Windows
instrument.bat .

# OU

# 4. Linux/Mac
./instrument.sh .
```

---

## ðŸ“‹ Passo-a-Passo RÃ¡pido

### Python FastAPI
```python
# 1. Adicione no TOPO do main.py
import otel_init

# 2. Resto do cÃ³digo normal
from fastapi import FastAPI
app = FastAPI()

# 3. Pronto! JÃ¡ estÃ¡ rastreando
```

### Node.js Express
```javascript
// 1. Adicione no TOPO do app.js
require('./otel-init.js');

// 2. Resto do cÃ³digo normal
const express = require('express');
const app = express();

// 3. Pronto! JÃ¡ estÃ¡ rastreando
```

### Java Spring Boot
```java
// 1. Importe OTelConfig
@Import(OTelConfig.class)

// 2. AnotaÃ§Ã£o na classe
@SpringBootApplication

// 3. Pronto! JÃ¡ estÃ¡ rastreando
```

### .NET ASP.NET
```csharp
// 1. Em Program.cs
builder.Services.AddLasOpenTelemetry();

// 2. Build & run
var app = builder.Build();

// 3. Pronto! JÃ¡ estÃ¡ rastreando
```

### PHP Laravel
```php
// 1. Em bootstrap/app.php
require_once __DIR__ . '/../otel-init.php';

// 2. Resto do cÃ³digo normal
$app = new Illuminate\Foundation\Application(...);

// 3. Pronto! JÃ¡ estÃ¡ rastreando
```

---

## ðŸŽ¯ Rastrear Evento Customizado

### Python
```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("meu-evento"):
    span.set_attribute("user.id", 123)
    # seu cÃ³digo
```

### Node.js
```javascript
const { trace } = require('@opentelemetry/api');
const tracer = trace.getTracer('app');

const span = tracer.startSpan('meu-evento');
span.setAttribute('user.id', 123);
// seu cÃ³digo
span.end();
```

### RUM (Browser)
```javascript
// AutomÃ¡tico
nexusRUM.trackEvent('signup', {
    'user.plan': 'pro'
});

// OperaÃ§Ã£o demorada
await nexusRUM.trackOperation('api-call', async () => {
    return await fetch('/api/data');
});
```

---

## ðŸ—‚ï¸ Documentos Importantes

| Preciso de... | Abrir... |
|---------------|----------|
| ComeÃ§ar agora | `START_HERE.md` |
| Entender tudo | `README.md` |
| ReferÃªncia | `REFERENCE.md` |
| Problema? | `TROUBLESHOOTING.md` |
| CI/CD | `CI-CD.md` |
| Exemplos | `examples/` |
| Menu | `python guide.py` |

---

## âš™ï¸ ConfiguraÃ§Ã£o BÃ¡sica

**Arquivo: `.env`**
```env
LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
SERVICE_NAME=meu-app
ENABLE_RUM=true
DEBUG_MODE=false
```

**Ambiente de Staging:**
```env
SERVICE_ENVIRONMENT=staging
TRACE_SAMPLE_RATE=1.0
DEBUG_MODE=true
```

**Ambiente de ProduÃ§Ã£o:**
```env
SERVICE_ENVIRONMENT=production
TRACE_SAMPLE_RATE=0.1  # 10% para reduzir custo
DEBUG_MODE=false
```

---

## ðŸš€ Deploy RÃ¡pido

### Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

### Kubernetes
```bash
kubectl apply -f deployment.yaml
kubectl set env deployment/app LAS_TOKEN=nxa_...
```

### GitHub Actions
```yaml
- name: Instrument
  run: python instrument.py . --enable-rum
```

---

## ðŸ” Debug RÃ¡pido

### Ativar debug
```bash
# Linux/Mac
export DEBUG_MODE=true

# Windows
set DEBUG_MODE=true

# PowerShell
$env:DEBUG_MODE="true"
```

### Ver logs
```bash
# Python
python main.py  # VerÃ¡ logs de OTel

# Node.js
npm start       # VerÃ¡ logs de OTel
```

### Testar conectividade
```bash
curl -v https://api.soservices.com.br:8443
```

---

## ðŸ“Š RUM - Rastrear UsuÃ¡rio

```javascript
// Quando usuÃ¡rio faz login
nexusRUM.setUserAttributes('user-123', {
    'user.email': 'john@example.com',
    'user.plan': 'pro',
    'user.org': 'acme'
});

// Rastrear aÃ§Ã£o
nexusRUM.trackEvent('purchase-completed', {
    'purchase.amount': 99.99,
    'purchase.currency': 'USD'
});

// Rastrear operaÃ§Ã£o demorada
const data = await nexusRUM.trackOperation('load-data', async () => {
    return fetch('/api/data');
});
```

---

## ðŸŽ¯ Verificar se Funciona

### 1. Checar inicializaÃ§Ã£o
```python
# No console vocÃª deve ver:
# âœ“ OpenTelemetry inicializado para LAS-worker
# Endpoint: https://api.soservices.com.br:8443/api/v1/ingest/otel
```

### 2. Fazer requisiÃ§Ã£o
```bash
# Python FastAPI
curl http://localhost:8000/api/tasks

# Node.js Express
curl http://localhost:8000/api/tasks

# Java Spring
curl http://localhost:8080/api/tasks
```

### 3. Verificar traces
```bash
# Em ~1-5 minutos, ir para:
https://las.soservices.com.br

# Procurar seu serviÃ§o em Services
# Verificar traces em Trace Explorer
```

---

## ðŸ’¡ Atalhos Ãšteis

### Script de Teste RÃ¡pido
```bash
# Python - Testar OTel
python -c "import otel_init; print('âœ“ OTel OK')"

# Node.js - Testar OTel
node -e "require('./otel-init.js'); console.log('âœ“ OTel OK')"
```

### Verificar VersÃµes
```bash
# Python
python -m pip list | grep opentelemetry

# Node.js
npm list | grep @opentelemetry
```

### Limpar e Reinstalar
```bash
# Python
pip uninstall opentelemetry-*
pip install -r requirements.txt

# Node.js
rm -rf node_modules package-lock.json
npm install
```

---

## ðŸ”’ SeguranÃ§a - mTLS

```env
MTLS_ENABLED=true
MTLS_CERT_PATH=/etc/certs/client.crt
MTLS_KEY_PATH=/etc/certs/client.key
MTLS_CA_PATH=/etc/certs/ca.crt
```

---

## ðŸ› Problemas RÃ¡pidos

| Problema | SoluÃ§Ã£o |
|----------|---------|
| "Module not found" | `pip install -r requirements.txt` |
| "Traces nÃ£o aparecem" | Ativar `DEBUG_MODE=true` |
| "Erro de conexÃ£o" | Verificar `LAS_TOKEN` |
| "RUM nÃ£o funciona" | Abrir console do navegador |
| "Porta em uso" | Mudar porta em config |

---

## ðŸ“¦ Requirements Python

```txt
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp>=0.41b0
opentelemetry-api>=1.20.0
opentelemetry-instrumentation-fastapi>=0.41b0
opentelemetry-instrumentation-psycopg2>=0.41b0
```

---

## ðŸ“¦ Pacotes Node.js

```bash
npm install @opentelemetry/sdk-node
npm install @opentelemetry/auto-instrumentations-node
npm install @opentelemetry/exporter-trace-otlp-http
```

---

## ðŸŽ¯ Spans Importantes

### HTTP Request
```python
span.set_attribute("http.method", "GET")
span.set_attribute("http.url", "/api/users")
span.set_attribute("http.status_code", 200)
```

### Database Query
```python
span.set_attribute("db.system", "postgresql")
span.set_attribute("db.statement", "SELECT * FROM users")
span.set_attribute("db.rows_affected", 5)
```

### Error
```python
span.record_exception(error)
span.set_attribute("error", True)
```

---

## ðŸ“ž Ajuda RÃ¡pida

### Ver menu interativo
```bash
python guide.py
```

### Ler documentaÃ§Ã£o
```bash
# START_HERE - COMECE AQUI!
cat START_HERE.md

# Completa
cat README.md

# Problemas
cat TROUBLESHOOTING.md
```

### Email
support@soservices.com.br

---

## âœ… Checklist RÃ¡pido (1 min)

- [ ] Fork/copiar otel-instrumentation/
- [ ] Editar .env com credentials
- [ ] Executar instrument.py
- [ ] Importar otel_init em cÃ³digo
- [ ] Rodar aplicaÃ§Ã£o
- [ ] Ver logs de inicializaÃ§Ã£o
- [ ] Fazer requisiÃ§Ã£o
- [ ] Verificar no LAS em 5 min

---

## ðŸš€ TL;DR (VersÃ£o Ultra Curta)

```bash
# 1. Copiar
cp -r otel-instrumentation /seu/projeto/

# 2. Config
echo "LAS_TOKEN=nxa_..." > .env

# 3. Instrument
python instrument.py .

# 4. Integrar
# import otel_init  (em Python)
# require('./otel-init.js');  (em Node.js)

# 5. Deploy
git push
python main.py
# ou npm start

# 6. Pronto! ðŸŽ‰
# Veja traces no https://las.soservices.com.br
```

---

**Para mais: [START_HERE.md](START_HERE.md) ou `python guide.py`** ðŸ‘ˆ

---

*Quick Reference - Framework OpenTelemetry para LAS*


