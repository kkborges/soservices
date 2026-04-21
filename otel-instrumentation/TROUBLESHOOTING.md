# ðŸ› Troubleshooting - ResoluÃ§Ã£o de Problemas

## âŒ Problemas Comuns

### 1. "Failed to connect to LAS endpoint"

**Sintoma:**
```
Error: Failed to connect to https://api.soservices.com.br:8443
```

**SoluÃ§Ãµes:**
- [ ] Verificar se o token estÃ¡ correto em `.env`
- [ ] Verificar endpoint: `https://api.soservices.com.br:8443/api/v1/ingest/otel`
- [ ] Testar conectividade:
  ```bash
  curl -v https://api.soservices.com.br:8443/api/v1/ingest/otel
  ```
- [ ] Se usar proxy, configurar em `.env`:
  ```env
  HTTPS_PROXY=http://proxy:8080
  ```
- [ ] Se usar firewall corporativo, liberar porta 8443

---

### 2. "Traces nÃ£o aparecem no LAS"

**Verificar checklist:**
- [ ] `otel_init` foi importado ANTES de qualquer outro cÃ³digo?
  ```python
  import otel_init  # â† Deve ser o PRIMEIRO import!
  from fastapi import FastAPI
  ```
- [ ] `.env` tem o token correto?
  ```env
  LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
  ```
- [ ] DependÃªncias instaladas?
  ```bash
  pip install -r requirements.txt  # ou npm install
  ```

**Ativar debug:**
```env
DEBUG_MODE=true
```

Isso vai exibir traces no console:
```
âœ“ OpenTelemetry inicializado
Span: fetch_data
  duration: 45ms
  status: OK
```

---

### 3. "Erro: ModuleNotFoundError: No module named 'opentelemetry'"

**SoluÃ§Ã£o:**
```bash
# Instalar pacotes
pip install -r requirements.txt

# Ou manualmente
pip install opentelemetry-sdk opentelemetry-exporter-otlp
```

**Se tiver venv/virtualenv ativado:**
```bash
python -m pip install --upgrade pip
python -m pip install opentelemetry-sdk
```

---

### 4. "Package.json nÃ£o foi modificado (Node.js)"

**Verificar:**
- [ ] `package.json` existe no diretÃ³rio?
- [ ] PermissÃµes de escrita?
  ```bash
  chmod +w package.json
  ```
- [ ] JSON vÃ¡lido? (nÃ£o pode ter comentÃ¡rios)

**SoluÃ§Ã£o manual:**
```bash
npm install @opentelemetry/sdk-node
npm install @opentelemetry/auto-instrumentations-node
npm install @opentelemetry/exporter-trace-otlp-http
```

---

### 5. "RUM nÃ£o funciona no navegador"

**Verificar DevTools:**
```javascript
// No console do navegador:
console.log(window.nexusRUM)  // Deve retornar objeto

// Rastrear evento manualmente:
nexusRUM.trackEvent('test-event')
```

**Se undefined:**
- [ ] `app.js` estÃ¡ sendo carregado?
  ```html
  <script src="/public/app.js"></script>
  ```
- [ ] Caminho estÃ¡ correto?
- [ ] CORS habilitado?

**Verificar logs HTML:**
```bash
# Abrir DevTools â†’ Console
# Procure por: "âœ“ RUM inicializado"
```

---

### 6. "mTLS: certificate verify failed"

**Se usar certificados:**
```env
MTLS_ENABLED=true
MTLS_CERT_PATH=/etc/certs/client.crt
MTLS_KEY_PATH=/etc/certs/client.key
MTLS_CA_PATH=/etc/certs/ca.crt
```

**Verificar certificados:**
```bash
# Validade
openssl x509 -in client.crt -noout -dates

# Formato
openssl x509 -in client.crt -noout -text | head -20

# Test
curl --cert client.crt --key client.key \
     --cacert ca.crt \
     https://api.soservices.com.br:8443
```

---

### 7. "Spans muito grandes / timeout"

**Sintoma:**
```
Error: Request timeout
```

**SoluÃ§Ãµes:**
- [ ] Reduzir tamanho de spans
- [ ] Aumentar batch size
- [ ] Ativar sampling:
  ```env
  TRACE_SAMPLE_RATE=0.1  # 10% dos traces
  ```

---

### 8. "Erro ao instrumentar: linguagem nÃ£o detectada"

**O script nÃ£o reconheceu a linguagem?**

**Verificar:**
- [ ] EstÃ¡ no diretÃ³rio raiz do projeto?
- [ ] Tem arquivo de dependÃªncias?
  - Python: `requirements.txt`, `setup.py`, `pyproject.toml`
  - Node: `package.json`
  - Java: `pom.xml`, `build.gradle`
  - .NET: `*.csproj`, `*.sln`
  - PHP: `composer.json`

**SoluÃ§Ã£o manual:**
Copiar template manualmente:
```bash
# Python
cp templates/python/otel_init.py ./

# Node.js
cp templates/nodejs/otel-init.js ./
```

---

## ðŸ” Debug AvanÃ§ado

### 1. Ativar verbose logging

```env
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

### 2. Testar exportador diretamente

**Python:**
```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
import os

exporter = OTLPSpanExporter(
    endpoint=os.getenv('LAS_ENDPOINT'),
    headers={"Authorization": f"Bearer {os.getenv('LAS_TOKEN')}"}
)

# Teste de conectividade
print("âœ“ Exporter criado com sucesso")
print(f"  Endpoint: {exporter._endpoint}")
```

**Node.js:**
```javascript
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');

const exporter = new OTLPTraceExporter({
    url: process.env.LAS_ENDPOINT,
    headers: { 'Authorization': `Bearer ${process.env.LAS_TOKEN}` }
});

console.log('âœ“ Exporter criado');
```

### 3. Interceptar requisiÃ§Ãµes

**Python (com requests):**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Node.js:**
```javascript
process.env.NODE_DEBUG = 'http,https';
```

---

## ðŸ“Š Checklist de DiagnÃ³stico

Antes de reportar problema, verificar:

- [ ] Token LAS vÃ¡lido
- [ ] Endpoint accessible
- [ ] DependÃªncias instaladas
- [ ] `otel_init` importado (primeiro import)
- [ ] `.env` no diretÃ³rio raiz
- [ ] PermissÃµes de arquivo
- [ ] Firewall/Proxy
- [ ] DEBUG_MODE ativado
- [ ] Sem erros no console

---

## ðŸ†˜ Ainda nÃ£o funciona?

### Coletar informaÃ§Ãµes de diagnÃ³stico

```bash
# Python
python -c "import opentelemetry; print(opentelemetry.__version__)"
cat las-config.example.env | grep -v '#'
cat requirements.txt | grep -i telemetry

# Node.js
npm list @opentelemetry/sdk-node
cat las-config.example.env | grep -v '#'
cat package.json | grep -i opentelemetry

# Java
mvn dependency:tree | grep opentelemetry

# .NET
dotnet package list | grep OpenTelemetry
```

### Verificar conectividade

```bash
# Testar endpoint
curl -X POST \
  -H "Authorization: Bearer lsa_SUBSTITUA_ESTE_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.soservices.com.br:8443/api/v1/ingest/otel

# Verificar DNS
nslookup api.soservices.com.br

# Verificar portas
telnet api.soservices.com.br 8443
```

### Ativa traÃ§os locais

```env
DEBUG_MODE=true
```

Isso vai exibir:
```
[otel] Span iniciado: fetch_data
[otel] Atributos: {'database': 'postgres', 'query': 'SELECT...'}
[otel] Span finalizado: 45ms
```

---

## ðŸ“ž Quando contactar suporte

Inclua:
1. VersÃ£o da linguagem (`python --version`)
2. Output de `DEBUG_MODE=true`
3. Resultado dos testes de conectividade
4. Stack trace completo
5. `.env` (sem token)
6. Arquivo de logs

**Email:** support@soservices.com.br  
**Docs:** https://las.soservices.com.br/troubleshooting

---

## ðŸ’¾ Backup da configuraÃ§Ã£o

Antes de fazer mudanÃ§as:
```bash
cp las-config.example.env las-config.example.env.backup
cp requirements.txt requirements.txt.backup
git add .
git commit -m "backup before otel changes"
```

---

**Dica:** Sempre comece com `DEBUG_MODE=true` para ver o que estÃ¡ acontecendo! ðŸ”

