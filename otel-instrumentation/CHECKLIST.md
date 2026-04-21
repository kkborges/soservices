# âœ… Checklist de ImplementaÃ§Ã£o

## ðŸ“¦ Framework OpenTelemetry para LAS - Checklist Completo

### âœ¨ Fase 1: PreparaÃ§Ã£o (5 min)

- [ ] Ler [START_HERE.md](START_HERE.md)
- [ ] Copiar `las-config.example.env` para seu projeto
- [ ] Editar `.env` com credenciais LAS
- [ ] Verificar se Python 3.8+ estÃ¡ instalado
- [ ] Copiar pasta `otel-instrumentation/` para seu projeto

### ðŸ”§ Fase 2: InstrumentaÃ§Ã£o (10 min)

#### Windows
```batch
cd C:\path\to\seu\projeto
instrument.bat .
```
- [ ] Script executou sem erros
- [ ] Dependencies foram adicionadas
- [ ] Arquivos de inicializaÃ§Ã£o foram criados
- [ ] RUM foi ativado (se escolheu)

#### Linux/Mac
```bash
cd /path/to/seu/projeto
./instrument.sh .
```
- [ ] Script executou sem erros
- [ ] Verificar output para confirmaÃ§Ã£o

#### PowerShell
```powershell
cd C:\path\to\seu\projeto
.\instrument.ps1
```
- [ ] Executou com sucesso

### ðŸ“ Fase 3: IntegraÃ§Ã£o (15 min)

#### Python (FastAPI/Django/Flask)
```python
import otel_init  # â† ADICIONAR NO TOPO!
from fastapi import FastAPI
app = FastAPI()
```
- [ ] `otel_init` adicionado como PRIMEIRO import
- [ ] Nenhum outro import antes dele
- [ ] `requirements.txt` atualizado
- [ ] Testar: `pip install -r requirements.txt`

#### Node.js (Express/NestJS)
```javascript
require('./otel-init.js');  // â† ADICIONAR NO TOPO!
const express = require('express');
```
- [ ] `otel-init.js` adicionado como PRIMEIRO require
- [ ] `package.json` atualizado com OTel
- [ ] Testar: `npm install`

#### Java (Spring Boot)
```java
@Import(OTelConfig.class)
@SpringBootApplication
public class Application {
    // seu cÃ³digo
}
```
- [ ] `OTelConfig.java` criado em `src/main/java/com/las/`
- [ ] Annotation `@Import` adicionada
- [ ] `pom.xml` ou `build.gradle` atualizado

#### .NET (ASP.NET)
```csharp
builder.Services.AddLasOpenTelemetry();
```
- [ ] `OTelConfig.cs` criado
- [ ] MÃ©todo chamado em `Program.cs`
- [ ] Pacotes NuGet instalados

#### PHP (Laravel/Symfony)
```php
<?php
require_once __DIR__ . '/otel-init.php';
```
- [ ] `otel-init.php` adicionado no arquivo de boot
- [ ] Composer executado: `composer install`

### ðŸŽ¯ Fase 4: RUM (5 min) - OPCIONAL

Se nÃ£o foi automÃ¡tico:

#### Em seu HTML/template
```html
<!-- Antes de </body> -->
<script src="/public/app.js"></script>
```

- [ ] `public/app.js` foi copiado
- [ ] Script tag adicionada no HTML
- [ ] AplicaÃ§Ã£o servindo arquivo estÃ¡tico

### ðŸš€ Fase 5: Deploy (5 min)

```bash
# Instalar dependÃªncias finais
pip install -r requirements.txt  # Python
npm install                       # Node.js
dotnet restore                    # .NET

# Fazer commit
git add .
git commit -m "chore: add OpenTelemetry instrumentation"
git push

# Deploy
python main.py                    # Python
npm start                         # Node.js
dotnet run                        # .NET
java -jar app.jar                 # Java
php artisan serve                 # PHP
```

- [ ] AplicaÃ§Ã£o iniciou sem erros
- [ ] Console nÃ£o mostra erros de OTel
- [ ] Se DEBUG_MODE=true, vÃª mensagem de inicializaÃ§Ã£o

### âœ… Fase 6: VerificaÃ§Ã£o (5 min)

#### No seu aplicativo:
- [ ] Fazer uma requisiÃ§Ã£o HTTP
- [ ] Fazer uma query ao banco de dados
- [ ] Gerar um erro (se possÃ­vel)

#### No navegador (se RUM estÃ¡ ativo):
- [ ] Abrir DevTools â†’ Console
- [ ] Procurar por: "âœ“ RUM inicializado"
- [ ] Clicar em um botÃ£o â†’ deve rastrear

#### No LAS:
- [ ] Ir para https://las.soservices.com.br
- [ ] Procurar seu serviÃ§o em "Services"
- [ ] Ver traces em "Trace Explorer"
- [ ] Verificar se aparecem com ~1-5 minutos de delay

### ðŸ” Troubleshooting RÃ¡pido

Se algo nÃ£o funcionou:

```bash
# Ativar debug
export DEBUG_MODE=true  # Linux/Mac
set DEBUG_MODE=true     # Windows

# Rodar aplicaÃ§Ã£o novamente
python main.py
```

- [ ] VocÃª vÃª logs de OTel no console?
- [ ] Token estÃ¡ correto em `.env`?
- [ ] DependÃªncias foram instaladas?
- [ ] `otel_init` estÃ¡ sendo importado?

Veja [TROUBLESHOOTING.md](TROUBLESHOOTING.md) para mais.

---

## ðŸ“Š Arquivos Criados - Checklist

### Scripts
- [x] `otel-instrumentation/instrument.py`
- [x] `otel-instrumentation/instrument.bat`
- [x] `otel-instrumentation/instrument.sh`
- [x] `otel-instrumentation/instrument.ps1`
- [x] `otel-instrumentation/guide.py`

### Templates
- [x] `otel-instrumentation/templates/python/otel_init.py`
- [x] `otel-instrumentation/templates/nodejs/otel-init.js`
- [x] `otel-instrumentation/templates/java/OTelConfig.java`
- [x] `otel-instrumentation/templates/dotnet/OTelConfig.cs`
- [x] `otel-instrumentation/templates/php/otel-init.php`

### RUM
- [x] `otel-instrumentation/rum/app.js`

### DocumentaÃ§Ã£o
- [x] `otel-instrumentation/START_HERE.md`
- [x] `otel-instrumentation/README.md`
- [x] `otel-instrumentation/REFERENCE.md`
- [x] `otel-instrumentation/TROUBLESHOOTING.md`
- [x] `otel-instrumentation/CI-CD.md`
- [x] `otel-instrumentation/SUMARIO.md`
- [x] `otel-instrumentation/CHECKLIST.md` â† Este arquivo

### Exemplos
- [x] `otel-instrumentation/examples/fastapi_example.py`
- [x] `otel-instrumentation/examples/express_example.js`
- [x] `otel-instrumentation/examples/spring_example.java`
- [x] `otel-instrumentation/examples/dotnet_example.cs`
- [x] `otel-instrumentation/examples/laravel_example.php`

### ConfiguraÃ§Ã£o
- [x] `otel-instrumentation/las-config.example.env`
- [x] `otel-instrumentation/requirements.txt`

---

## ðŸŽ¯ PrÃ³ximas AÃ§Ãµes

### Imediato (agora)
- [ ] Executar `python guide.py` para menu interativo
- [ ] Ler [START_HERE.md](START_HERE.md)
- [ ] Copiar framework para seu projeto

### Esta semana
- [ ] Instrumentar seu primeiro projeto
- [ ] Testar em ambiente de staging
- [ ] Verificar traces no LAS
- [ ] Customizar spans conforme necessÃ¡rio

### Este mÃªs
- [ ] Instrumentar todos os serviÃ§os crÃ­ticos
- [ ] Ativar RUM em aplicaÃ§Ãµes web
- [ ] Configurar alertas no LAS
- [ ] Criar dashboards customizados
- [ ] Integrar em CI/CD

### Longo prazo
- [ ] Treinar time em OTel
- [ ] Documentar padrÃµes de tracing
- [ ] Estabelecer SLOs
- [ ] Otimizar sampling rates
- [ ] IntegraÃ§Ã£o com observabilidade existente

---

## ðŸ“ž Suporte & Recursos

### DocumentaÃ§Ã£o
- [LAS Platform](https://las.soservices.com.br)
- [OpenTelemetry](https://opentelemetry.io)
- [OTLP Protocol](https://opentelemetry.io/docs/reference/protocol/)

### Menu Interativo
```bash
python guide.py
```

### Para Problemas
1. Verificar [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Ativar `DEBUG_MODE=true`
3. Consultar examples/
4. Contactar support@soservices.com.br

---

## ðŸ† Sucesso!

Se vocÃª completar este checklist:

âœ… Sua aplicaÃ§Ã£o estÃ¡ instrumentada
âœ… Traces estÃ£o sendo enviados para LAS
âœ… RUM estÃ¡ monitorando experiÃªncia do usuÃ¡rio
âœ… VocÃª tem visibilidade total da sua aplicaÃ§Ã£o
âœ… Pode criar dashboards e alertas
âœ… EstÃ¡ pronto para debugging avanÃ§ado

---

**Data de conclusÃ£o: ________________**

**ResponsÃ¡vel: ________________**

**Notas:**
```
_________________________________
_________________________________
_________________________________
```

---

*Framework OpenTelemetry para LAS - Pronto para usar!* ðŸš€

