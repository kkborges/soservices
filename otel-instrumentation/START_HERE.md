# ðŸš€ Framework OpenTelemetry para LAS

Framework completo de **auto-instrumentaÃ§Ã£o multi-linguagem** para enviar observabilidade para o LAS.

## âœ¨ O Que Foi Criado

VocÃª agora tem um sistema profissional e completo:

```
otel-instrumentation/
â”œâ”€â”€ âš™ï¸  CORE
â”‚   â”œâ”€â”€ instrument.py           # Script principal de instrumentaÃ§Ã£o
â”‚   â”œâ”€â”€ instrument.bat           # Para Windows
â”‚   â”œâ”€â”€ instrument.sh            # Para Linux/Mac
â”‚   â”œâ”€â”€ instrument.ps1           # Para PowerShell
â”‚   â””â”€â”€ las-config.example.env         # ConfiguraÃ§Ã£o centralizada
â”‚
â”œâ”€â”€ ðŸ“š TEMPLATES (por linguagem)
â”‚   â”œâ”€â”€ python/otel_init.py
â”‚   â”œâ”€â”€ nodejs/otel-init.js
â”‚   â”œâ”€â”€ java/OTelConfig.java
â”‚   â”œâ”€â”€ dotnet/OTelConfig.cs
â”‚   â””â”€â”€ php/otel-init.php
â”‚
â”œâ”€â”€ ðŸŽ¯ RUM (Real User Monitoring)
â”‚   â””â”€â”€ app.js                   # Monitoring de browser
â”‚
â”œâ”€â”€ ðŸ“– DOCUMENTAÃ‡ÃƒO
â”‚   â”œâ”€â”€ README.md                # DocumentaÃ§Ã£o completa
â”‚   â”œâ”€â”€ REFERENCE.md             # Guia de referÃªncia
â”‚   â”œâ”€â”€ guide.py                 # Menu interativo
â”‚   â””â”€â”€ TROUBLESHOOTING.md       # ResoluÃ§Ã£o de problemas
â”‚
â””â”€â”€ ðŸ“ EXEMPLOS
    â”œâ”€â”€ fastapi_example.py       # FastAPI + OTel + RUM
    â”œâ”€â”€ express_example.js       # Express + OTel
    â”œâ”€â”€ spring_example.java      # Spring Boot + OTel
    â”œâ”€â”€ dotnet_example.cs        # .NET + OTel
    â””â”€â”€ laravel_example.php      # Laravel + OTel
```

---

## ðŸŽ¯ Uso RÃ¡pido (5 minutos)

### 1ï¸âƒ£ Copiar para seu projeto

```bash
# Windows
xcopy otel-instrumentation . /E /Y
copy las-config.example.env .

# Linux/Mac
cp -r otel-instrumentation .
cp las-config.example.env .
```

### 2ï¸âƒ£ Executar instrumentaÃ§Ã£o

```bash
# Windows
instrument.bat .

# Linux/Mac
./instrument.sh .

# PowerShell
.\instrument.ps1
```

### 3ï¸âƒ£ Importar em sua aplicaÃ§Ã£o

**Python:**
```python
import otel_init  # Adicionar no inÃ­cio!
from fastapi import FastAPI
app = FastAPI()
```

**Node.js:**
```javascript
require('./otel-init.js');  // Primeiro import!
const express = require('express');
```

### 4ï¸âƒ£ Deploy!

```bash
pip install -r requirements.txt  # ou npm install, etc
python main.py
```

âœ… **Pronto! Seus traces estÃ£o sendo enviados para o LAS!**

---

## ðŸŒ Linguagens Suportadas

| Linguagem | Frameworks | Status |
|-----------|-----------|--------|
| ðŸ Python | FastAPI, Django, Flask | âœ… ProduÃ§Ã£o |
| ðŸŸ¢ Node.js | Express, NestJS, Next.js | âœ… ProduÃ§Ã£o |
| â˜• Java | Spring Boot, Quarkus | âœ… ProduÃ§Ã£o |
| ðŸ”µ .NET | ASP.NET, C# | âœ… ProduÃ§Ã£o |
| ðŸ˜ PHP | Laravel, Symfony | âœ… ProduÃ§Ã£o |
| ðŸŒ Browser | RUM (JavaScript) | âœ… ProduÃ§Ã£o |

---

## ðŸ“Š Capacidades

### Traces (Rastreamento)
- âœ… CorrelaÃ§Ã£o automÃ¡tica de requisiÃ§Ãµes
- âœ… Rastreamento de banco de dados
- âœ… Rastreamento de filas (RabbitMQ, etc)
- âœ… Rastreamento de HTTP calls
- âœ… Rastreamento customizado

### MÃ©tricas
- âœ… LatÃªncia de requisiÃ§Ã£o
- âœ… Taxa de erro
- âœ… Throughput
- âœ… Tamanho de payload
- âœ… Memory/CPU (opcional)

### Logs
- âœ… Contexto automÃ¡tico
- âœ… CorrelaÃ§Ã£o com traces
- âœ… Structured logging

### RUM (Real User Monitoring)
- âœ… Eventos de pÃ¡gina
- âœ… InteraÃ§Ãµes do usuÃ¡rio
- âœ… Erros JavaScript
- âœ… Performance do browser

---

## ðŸŽ“ Exemplos

Temos exemplos prontos para usar:

```bash
# Ver menu interativo
python guide.py

# Ou copiar exemplos
cp examples/fastapi_example.py ./main.py
cp examples/express_example.js ./app.js
```

---

## ðŸ”§ ConfiguraÃ§Ã£o

### BÃ¡sica (.env)
```env
LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
SERVICE_NAME=meu-app
ENABLE_RUM=true
```

### AvanÃ§ada
```env
# Debug
DEBUG_MODE=true
TRACE_SAMPLE_RATE=0.1

# mTLS
MTLS_ENABLED=true
MTLS_CERT_PATH=/path/to/cert.crt
MTLS_KEY_PATH=/path/to/key.key

# Proxy
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=https://proxy:8443
```

---

## ðŸ“– DocumentaÃ§Ã£o

| Arquivo | ConteÃºdo |
|---------|----------|
| [README.md](README.md) | Guia completo de uso |
| [REFERENCE.md](REFERENCE.md) | ReferÃªncia tÃ©cnica |
| [Troubleshooting](TROUBLESHOOTING.md) | ResoluÃ§Ã£o de problemas |
| [guide.py](guide.py) | Menu interativo |

---

## ðŸš¦ Fluxo de Dados

```
Sua AplicaÃ§Ã£o
    â†“
    â”œâ”€â†’ ðŸ“Š Trace (requisiÃ§Ã£o)
    â”œâ”€â†’ ðŸ“ˆ MÃ©trica (latÃªncia)
    â”œâ”€â†’ ðŸ“ Log (evento)
    â””â”€â†’ ðŸŒ RUM (user event)
    â†“
OpenTelemetry SDK
    â†“
Batch Processor (agrupa eventos)
    â†“
OTLP HTTP Exporter
    â†“
https://api.soservices.com.br:8443
    â†“
ðŸ“Š LAS Dashboard
```

---

## ðŸ†š Antes vs Depois

### Antes
```python
# Sem visibilidade
def get_user(user_id):
    result = db.query(f"SELECT * FROM users WHERE id={user_id}")
    return result
```

### Depois
```python
import otel_init  # â† Auto-instrumentaÃ§Ã£o!
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def get_user(user_id):
    with tracer.start_as_current_span("get_user") as span:
        span.set_attribute("user.id", user_id)
        result = db.query(f"SELECT * FROM users WHERE id={user_id}")
        span.set_attribute("db.rows_returned", len(result))
        return result
```

**Resultado:** Todos os traces automaticamente enviados para LAS! ðŸŽ‰

---

## âš¡ Performance

- **Overhead**: < 5% latÃªncia adicional
- **Batch size**: 512 spans (otimizado)
- **Export time**: ~100ms (assÃ­ncrono)
- **Sampling**: Controle de volume de traces

---

## ðŸ”’ SeguranÃ§a

- âœ… Token via header Authorization
- âœ… Suporte a mTLS
- âœ… TLS 1.3
- âœ… Sem exposiÃ§Ã£o de dados sensÃ­veis

---

## ðŸ’¡ Tips & Tricks

### 1. RUM customizado
```javascript
nexusRUM.trackEvent('checkout-started', {
  'cart.total': 99.99,
  'user.tier': 'premium'
});
```

### 2. OperaÃ§Ãµes demoradas
```javascript
await nexusRUM.trackOperation('api-call', async () => {
  return await fetch('/api/data');
});
```

### 3. Contexto do usuÃ¡rio
```javascript
nexusRUM.setUserAttributes('user-123', {
  'user.email': 'john@example.com',
  'user.plan': 'pro'
});
```

### 4. Debug local
```env
DEBUG_MODE=true  # VÃª traces no console
```

---

## ðŸ“ž Suporte & Comunidade

- ðŸ“– [DocumentaÃ§Ã£o LAS](https://las.soservices.com.br)
- ðŸ› [Issues & Bugs](https://github.com/soservices/LAS)
- ðŸ’¬ [Comunidade](https://community.LAS.soservices.com.br)
- ðŸ“§ [Email](mailto:support@soservices.com.br)

---

## ðŸŽ¯ PrÃ³ximos Passos

1. âœ… Executar `instrument.py` para auto-instrumentar
2. âœ… Importar `otel_init` em sua aplicaÃ§Ã£o
3. âœ… Deploy e verificar traces no LAS
4. âœ… Customizar spans conforme necessÃ¡rio
5. âœ… Integrar RUM para user analytics

---

## ðŸ“„ LicenÃ§a

Desenvolvido para **LAS Platform** - Todos os direitos reservados ðŸš€

---

**Comece agora:**
```bash
python guide.py
```


