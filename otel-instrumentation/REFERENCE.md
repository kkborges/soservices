# ðŸ“– Guia Completo de ReferÃªncia

## ðŸš€ Uso RÃ¡pido

### Para Windows:
```batch
instrument.bat C:\path\to\seu\projeto --enable-rum
```

### Para Linux/Mac:
```bash
./instrument.sh /path/to/seu/projeto --enable-rum
```

### Para PowerShell:
```powershell
.\instrument.ps1 -ProjectPath "." -EnableRUM $true
```

---

## ðŸ” Credenciais LAS

**Token:** `lsa_SUBSTITUA_ESTE_TOKEN`

**Endpoint:** `https://api.soservices.com.br:8443/api/v1/ingest/otel`

Configure em `.env`:
```env
LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
LAS_ENDPOINT=https://api.soservices.com.br:8443/api/v1/ingest/otel
SERVICE_NAME=meu-app
ENABLE_RUM=true
```

---

## ðŸ“Š Arquitetura

```
Sua AplicaÃ§Ã£o
    â†“
OpenTelemetry SDK
    â†“
OTLP Exporter
    â†“
LAS Platform
    â†“
Dashboards, Traces, MÃ©tricas, Logs
```

---

## ðŸ”„ Fluxo de InstrumentaÃ§Ã£o

1. **DetecÃ§Ã£o automÃ¡tica** de linguagem/framework
2. **AdiÃ§Ã£o de dependÃªncias** (pip, npm, Maven, etc)
3. **CÃ³pia de arquivos de configuraÃ§Ã£o**
4. **AdiÃ§Ã£o de RUM** (opcional)
5. **Pronto para usar!**

---

## ðŸ“¦ Estrutura de DiretÃ³rios

```
seu-projeto/
â”œâ”€â”€ las-config.example.env
â”œâ”€â”€ otel-instrumentation/
â”‚   â”œâ”€â”€ instrument.py
â”‚   â”œâ”€â”€ templates/
â”‚   â”‚   â”œâ”€â”€ python/otel_init.py
â”‚   â”‚   â”œâ”€â”€ nodejs/otel-init.js
â”‚   â”‚   â”œâ”€â”€ java/OTelConfig.java
â”‚   â”‚   â”œâ”€â”€ dotnet/OTelConfig.cs
â”‚   â”‚   â””â”€â”€ php/otel-init.php
â”‚   â””â”€â”€ rum/app.js
â”œâ”€â”€ public/
â”‚   â””â”€â”€ app.js  â† RUM para browser
â””â”€â”€ main.py (ou index.js, etc)
```

---

## ðŸŽ¯ Casos de Uso

### Caso 1: FastAPI + PostgreSQL
- âœ“ Rastreia requisiÃ§Ãµes HTTP
- âœ“ Rastreia queries ao banco de dados
- âœ“ Rastreia erros
- âœ“ Mede performance

### Caso 2: Express + RabbitMQ
- âœ“ Rastreia processamento de filas
- âœ“ Correlaciona mensagens
- âœ“ Monitora latÃªncia

### Caso 3: SPA com React
- âœ“ RUM rastreia interaÃ§Ãµes
- âœ“ Monitora experiÃªncia do usuÃ¡rio
- âœ“ Detecta erros em tempo real

---

## ðŸ”— CorrelaÃ§Ã£o de Traces

O OpenTelemetry automaticamente correlaciona traces atravÃ©s de:
- **Trace ID**: Identifica a requisiÃ§Ã£o
- **Span ID**: Identifica operaÃ§Ã£o especÃ­fica
- **Parent Span ID**: Conecta chamadas aninhadas

Resultado: VocÃª vÃª toda a jornada da requisiÃ§Ã£o! ðŸŽ¯

---

## ðŸ“ˆ MÃ©tricas Capturadas

- **LatÃªncia**: Tempo de resposta
- **Taxa de erro**: Erros por segundo
- **Throughput**: RequisiÃ§Ãµes por segundo
- **Tamanho de payload**: Bytes enviados/recebidos
- **Memory**: Consumo de memÃ³ria (opcional)
- **CPU**: Uso de CPU (opcional)

---

## ðŸŽ¨ RUM - Eventos Rastreados

### AutomÃ¡ticos
- Page load
- Navigation
- JavaScript errors
- Unhandled rejections
- User clicks
- Form submissions
- Input changes

### Customizados
```javascript
nexusRUM.trackEvent('custom-event', {
    'custom.field': 'value',
    'timestamp': Date.now()
});
```

---

## ðŸ”’ SeguranÃ§a

### mTLS
Para ambientes que requerem certificado cliente:

```env
MTLS_ENABLED=true
MTLS_CERT_PATH=/path/to/client.crt
MTLS_KEY_PATH=/path/to/client.key
MTLS_CA_PATH=/path/to/ca.crt
```

### Headers
Token Ã© enviado via header Authorization:
```
Authorization: Bearer lsa_SUBSTITUA_ESTE_TOKEN
```

---

## ðŸš¦ Sampling

Controle quantos traces enviar:
```env
TRACE_SAMPLE_RATE=0.1  # 10% dos traces (reduz custos)
TRACE_SAMPLE_RATE=1.0  # 100% dos traces (mais detalhes)
```

---

## ðŸ³ Docker

Para dockerizar sua aplicaÃ§Ã£o instrumentada:

```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
COPY las-config.example.env .env
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

**mTLS no Docker:**
```dockerfile
COPY certs/client.crt /etc/certs/
COPY certs/client.key /etc/certs/
ENV MTLS_CERT_PATH=/etc/certs/client.crt
ENV MTLS_KEY_PATH=/etc/certs/client.key
```

---

## ðŸ’» VariÃ¡veis de Ambiente

| VariÃ¡vel | PadrÃ£o | DescriÃ§Ã£o |
|----------|--------|-----------|
| `LAS_ENDPOINT` | `https://api.soservices.com.br:8443/api/v1/ingest/otel` | URL do LAS |
| `LAS_TOKEN` | `` | Token de autenticaÃ§Ã£o |
| `SERVICE_NAME` | `application` | Nome do serviÃ§o |
| `SERVICE_VERSION` | `1.0.0` | VersÃ£o do serviÃ§o |
| `SERVICE_ENVIRONMENT` | `production` | prod/staging/dev |
| `ENABLE_RUM` | `true` | Habilitar RUM |
| `ENABLE_METRICS` | `true` | Habilitar mÃ©tricas |
| `TRACE_SAMPLE_RATE` | `1.0` | Taxa de sampling |
| `DEBUG_MODE` | `false` | Exibir traces no console |
| `MTLS_ENABLED` | `false` | Usar certificados mTLS |

---

## ðŸ”— Links Ãšteis

- [LAS Documentation](https://las.soservices.com.br)
- [OpenTelemetry Docs](https://opentelemetry.io)
- [OTLP Protocol](https://opentelemetry.io/docs/reference/protocol/)
- [Semantic Conventions](https://opentelemetry.io/docs/reference/specification/protocol/exporter/)

---

## ðŸ“ž Suporte

Para problemas ou dÃºvidas:
1. Verifique [Troubleshooting](TROUBLESHOOTING.md)
2. Execute `guide.py` para menu interativo
3. Consulte exemplos em `examples/`
4. Verifique documentaÃ§Ã£o oficial do LAS

---

**Desenvolvido para LAS Platform** ðŸš€

