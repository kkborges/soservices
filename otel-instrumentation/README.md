# ðŸ“Š OpenTelemetry Auto-Instrumentador para LAS

Framework de auto-instrumentaÃ§Ã£o multi-linguagem para enviar mÃ©tricas, traces e logs para a plataforma **LAS**.

## ðŸš€ Quick Start

### 1. Clonar/Copiar para seu projeto

```bash
cd /caminho/do/seu/projeto
cp -r /caminho/do/LAS/otel-instrumentation .
cp otel-instrumentation/las-config.example.env .env
```

### 2. Configurar credenciais

Edite `.env`:
```env
LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
SERVICE_NAME=meu-app
ENABLE_RUM=true
```

### 3. Instrumentar seu projeto

```bash
python otel-instrumentation/instrument.py . --enable-rum
```

Pronto! O script vai:
- âœ“ Detectar linguagem/framework
- âœ“ Adicionar dependÃªncias
- âœ“ Criar arquivos de inicializaÃ§Ã£o
- âœ“ Adicionar RUM (opcional)

---

## ðŸ“‹ Linguagens Suportadas

### Python

**Antes:**
```python
from fastapi import FastAPI

app = FastAPI()
```

**Depois:**
```python
import otel_init  # Adicionar import no inÃ­cio!
from fastapi import FastAPI

app = FastAPI()
```

### Node.js

**Antes:**
```javascript
const express = require('express');
const app = express();
```

**Depois:**
```javascript
require('./otel-init.js');  // Adicionar no inÃ­cio!
const express = require('express');
const app = express();
```

**No package.json:**
```bash
npm install
```

### Java (Spring Boot)

**Em `application.yml`:**
```yaml
server:
  port: 8080

spring:
  application:
    name: meu-app
```

**Em `build.gradle`:**
```gradle
dependencies {
    implementation 'io.opentelemetry.javaagent:opentelemetry-javaagent:1.32.0'
}
```

**Executar com:**
```bash
java -javaagent:./opentelemetry-javaagent.jar \
     -Dotel.exporter.otlp.endpoint=https://api.soservices.com.br:8443 \
     -Dotel.service.name=meu-app \
     -jar app.jar
```

### .NET

**Em `Program.cs`:**
```csharp
using LAS.Instrumentation;

var builder = WebApplication.CreateBuilder(args);

// Adicionar
builder.Services.AddLasOpenTelemetry();

var app = builder.Build();
```

Instalar pacotes:
```bash
dotnet add package OpenTelemetry
dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol
dotnet add package OpenTelemetry.Instrumentation.AspNetCore
```

### PHP

**No seu arquivo de entrada (index.php ou config):**
```php
<?php
require_once __DIR__ . '/otel-init.php';

// Seu cÃ³digo
?>
```

Instalar via Composer:
```bash
composer require open-telemetry/api
composer require open-telemetry/sdk
composer require open-telemetry/exporter-otlp
```

---

## ðŸŽ¯ RUM (Real User Monitoring)

### Ativar RUM

Se nÃ£o ativou durante a instrumentaÃ§Ã£o, adicione manualmente:

**Em seu HTML (antes de `</body>`):**
```html
<script src="/public/app.js"></script>
```

### Rastreamento AutomÃ¡tico

O RUM rastreia automaticamente:
- âœ“ Carregamento de pÃ¡gina
- âœ“ NavegaÃ§Ã£o SPA
- âœ“ Erros JavaScript
- âœ“ Promise rejections
- âœ“ Cliques
- âœ“ SubmissÃµes de formulÃ¡rio
- âœ“ MudanÃ§as em inputs

### Rastreamento Customizado

```javascript
// Rastrear evento customizado
nexusRUM.trackEvent('user-signup', {
    'user.plan': 'premium',
    'signup.method': 'google'
});

// Rastrear operaÃ§Ã£o demorada
await nexusRUM.trackOperation('fetch-data', async () => {
    const resp = await fetch('/api/data');
    return resp.json();
});

// Definir contexto do usuÃ¡rio
nexusRUM.setUserAttributes('user-123', {
    'user.email': 'user@example.com',
    'user.plan': 'pro',
});
```

---

## ðŸ”§ ConfiguraÃ§Ã£o AvanÃ§ada

### Certificados mTLS

Se usar mTLS, configure em `.env`:
```env
MTLS_ENABLED=true
MTLS_CERT_PATH=/path/to/client.crt
MTLS_KEY_PATH=/path/to/client.key
MTLS_CA_PATH=/path/to/ca.crt
```

### Taxa de Sampling

Controle quantos traces enviar:
```env
TRACE_SAMPLE_RATE=0.1  # 10% dos traces
```

### Debug Mode

```env
DEBUG_MODE=true
```

Isso vai exibir traces no console em vez de enviar para LAS.

---

## ðŸ“Š Estrutura de DiretÃ³rios

```
otel-instrumentation/
â”œâ”€â”€ las-config.example.env              # ConfiguraÃ§Ã£o centralizada
â”œâ”€â”€ instrument.py                 # Script de auto-instrumentaÃ§Ã£o
â”œâ”€â”€ templates/
â”‚   â”œâ”€â”€ python/
â”‚   â”‚   â””â”€â”€ otel_init.py
â”‚   â”œâ”€â”€ nodejs/
â”‚   â”‚   â””â”€â”€ otel-init.js
â”‚   â”œâ”€â”€ java/
â”‚   â”‚   â””â”€â”€ OTelConfig.java
â”‚   â”œâ”€â”€ dotnet/
â”‚   â”‚   â””â”€â”€ OTelConfig.cs
â”‚   â””â”€â”€ php/
â”‚       â””â”€â”€ otel-init.php
â”œâ”€â”€ rum/
â”‚   â””â”€â”€ app.js                    # RUM para browser
â””â”€â”€ README.md
```

---

## ðŸ› Troubleshooting

### Erros de ConexÃ£o

```
Error: Failed to connect to https://api.soservices.com.br:8443
```

Verificar:
1. âœ“ Token correto em `.env`
2. âœ“ Endpoint correto
3. âœ“ Firewall/proxy

### Traces nÃ£o aparecem

1. âœ“ Verificar se `otel_init.py` / `otel-init.js` estÃ¡ sendo importado
2. âœ“ Ativar `DEBUG_MODE=true` para ver traces localmente
3. âœ“ Verificar logs da aplicaÃ§Ã£o

### RUM nÃ£o funciona

1. âœ“ Verificar se `app.js` estÃ¡ sendo carregado
2. âœ“ Abrir DevTools â†’ Console para erros
3. âœ“ Verificar se `ENABLE_RUM=true` em `.env`

---

## ðŸ“ Exemplo Completo: FastAPI com RUM

**requirements.txt:**
```
fastapi==0.100.0
uvicorn==0.24.0
opentelemetry-sdk==1.20.0
opentelemetry-exporter-otlp==0.41b0
opentelemetry-instrumentation-fastapi==0.41b0
```

**main.py:**
```python
import otel_init  # â† Primeiro import!
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
async def root():
    return HTMLResponse("""
    <html>
        <head><title>Meu App</title></head>
        <body>
            <h1>Bem-vindo!</h1>
            <button onclick="nexusRUM.trackEvent('welcome-click')">
                Clique aqui
            </button>
            <script src="/app.js"></script>
        </body>
    </html>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## ðŸ¤ Support

DÃºvidas? Verifique:
- [LAS Documentation](https://las.soservices.com.br)
- [OpenTelemetry Docs](https://opentelemetry.io)

---

**Desenvolvido para LAS Platform** ðŸš€


