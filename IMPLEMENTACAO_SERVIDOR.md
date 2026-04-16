# 🚀 GUIA DE IMPLEMENTAÇÃO - NEXUS-2.0 NO SERVIDOR

**Status**: Ready to Execute  
**Servidor**: 192.168.0.108  
**Usuário**: kleber / sudo  
**Diretório**: /srv/Projetos/nexus-2.0  
**Recursos**: 24 vCPU, 189 GB RAM

---

## ✅ PRÉ-REQUISITOS VERIFICADOS

- [ ] Chave SSH configurada em `~/.ssh/config`
- [ ] Git instalado no servidor
- [ ] Python 3.12+ instalado
- [ ] Docker e Docker Compose funcionando
- [ ] Acesso SSH/SCP liberado

---

## 📋 FASE 1: PREPARAÇÃO DO SERVIDOR

### 1.1 Conectar ao Servidor

```bash
# SSH direto
ssh kleber@192.168.0.108

# Ou adicionar em ~/.ssh/config
Host nexus-dev
    HostName 192.168.0.108
    User kleber
    IdentityFile ~/.ssh/id_rsa
    
# Depois usar: ssh nexus-dev
```

### 1.2 Preparar Diretórios

```bash
# Conectado no servidor
ssh kleber@192.168.0.108

# Criar estrutura
mkdir -p /srv/Projetos/nexus-2.0
cd /srv/Projetos/nexus-2.0

# Caso precise permissões root
sudo chown -R kleber:kleber /srv/Projetos
```

### 1.3 Clonar Repositório

```bash
# No servidor, dentro /srv/Projetos/nexus-2.0
cd /srv/Projetos/nexus-2.0

# Clone o repositório GitHub
git clone https://github.com/soservices/nexus.git .

# Ou se for primeira vez:
git clone https://github.com/soservices/nexus.git nexus-2.0
cd nexus-2.0
```

### 1.4 Verificar Estrutura

```bash
# Verificar que estrutura de testes foi criada
ls -la tests/backend/
ls -la tests/backend/unit/
ls -la tests/backend/integration/

# Verificar GitHub Actions
ls -la .github/workflows/
```

---

## 📦 FASE 2: SETUP LOCAL (DESENVOLVIMENTO)

### 2.1 Instalar Python Virtual Environment

```bash
cd /srv/Projetos/nexus-2.0

# Criar venv
python3.12 -m venv venv

# Ativar venv
source venv/bin/activate  # Linux/Mac
# Ou no Windows: venv\Scripts\activate

# Verificar Python
python --version  # Deve ser 3.12+
```

### 2.2 Instalar Dependências

```bash
# Ambiente ativado
cd backend

# Instalar dependências principais
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Instalar dependências de desenvolvimento (IMPORTANTE!)
pip install -r requirements-dev.txt

# Verificar instalação
pip list | grep pytest
pip list | grep black
pip list | grep pylint
```

### 2.3 Configurar Variáveis de Ambiente

```bash
# No /srv/Projetos/nexus-2.0/backend/
cat > .env.test << 'EOF'
# Test Environment Variables
TESTING=true
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key-123456789012345678
APP_NAME=Nexus Test
APP_VERSION=3.0.0-test
MTLS_ENABLED=false
MTLS_REQUIRED=false
EOF

# Ou para testes com BD real:
cat > .env.test-db << 'EOF'
DATABASE_URL=postgresql://kleber:password@localhost/nexus_test
REDIS_URL=redis://localhost:6379/1
TESTING=true
EOF
```

---

## ✅ FASE 3: RODAR TESTES LOCALMENTE

### 3.1 Teste Básico - Health Check

```bash
# No /srv/Projetos/nexus-2.0/backend/
cd /srv/Projetos/nexus-2.0/backend

# Executar pytest descoberta
pytest --collect-only ../tests/backend/

# Deve listar ~30+ testes encontrados
```

### 3.2 Rodar Testes Unitários

```bash
# Testes rápidos (sem dependências externas)
pytest ../tests/backend/unit -v

# Expected output:
# ✅ test_auth_service.py - 15 testes passando
# ✅ test_schemas.py - 10 testes passando
```

### 3.3 Rodar Testes de Integração

```bash
# Testes que requerem serviços
# Antes, certifique que PostgreSQL/Redis estão rodando

# Opção 1: Com Docker Compose
cd /srv/Projetos/nexus-2.0/docker
docker compose up -d postgres redis  # Iniciar serviços

# Opção 2: Verificar se já estão rodando
docker ps | grep postgres
docker ps | grep redis

# Agora rodar testes
cd /srv/Projetos/nexus-2.0
pytest tests/backend/integration -v
```

### 3.4 Cobertura Completa

```bash
# Rodar com coverage report
pytest tests/backend \
  -v \
  --cov=app \
  --cov-report=term \
  --cov-report=html

# Output esperado:
# ============ test session starts =============
# collected 30+ items
# tests/backend/unit/test_auth_service.py::TestPasswordHashing::test_hash_password PASSED
# ...
# ============ 30+ passed in X.XXs =============
# 
# Coverage: XX%

# Verificar relatório HTML
ls -la coverage_html/index.html
```

### 3.5 Testes em Paralelo (Rápido!)

```bash
# Instalar plugin de paralelismo
pip install pytest-xdist

# Rodar em paralelo (muito mais rápido)
pytest tests/backend -n auto
```

---

## 🔍 FASE 4: EXECUTAR CODE QUALITY

### 4.1 Linting com Pylint

```bash
cd /srv/Projetos/nexus-2.0/backend

# Verificar qualidade de código
pylint app --disable=R,C --fail-under=7.0

# Esperado: Score 7.0+ ou success
```

### 4.2 Type Checking com MyPy

```bash
# Verificar tipos
mypy app --ignore-missing-imports

# Esperado: "Success: no issues found" ou poucas warnings
```

### 4.3 Formatação com Black

```bash
# Verificar formatação
black --check app

# Se houver problemas, corrigir:
black app
git diff app/  # Ver o que mudou
```

### 4.4 Organizar Imports com isort

```bash
# Verificar importações
isort --check-only app

# Se houver problemas, corrigir:
isort app
git diff app/  # Ver o que mudou
```

---

## 🔐 FASE 5: CONFIGURAR GITHUB (IMPORTANTE!)

### 5.1 Adicionar Secrets ao GitHub

Necessários para CI/CD funcionar:

```bash
# No GitHub: Settings > Secrets > Actions > New repository secret

# Para DEV deployment:
DEV_HOST = 192.168.0.108
DEV_USER = kleber
DEV_SSH_KEY = (conteúdo da chave privada)

# Para PROD (depois):
PROD_HOST = seu-servidor-prod.com
PROD_USER = deploy-user
PROD_SSH_KEY = (chave privada)

# Slack notifications (opcional):
SLACK_WEBHOOK_URL = https://hooks.slack.com/services/...
```

### 5.2 Gerar SSH Key (Se não existir)

```bash
# No seu computador local
ssh-keygen -t rsa -b 4096 -f ~/.ssh/github_deploy

# Conteúdo da chave pública para servidor:
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys

# Copiar conteúdo da chave privada para GitHub Secret:
cat ~/.ssh/github_deploy
# Copiar toda saída (-----BEGIN... até END----)
```

### 5.3 Testar GitHub Actions

```bash
# Fazer commit de um teste trivial
git add .
git commit -m "chore: add CI/CD pipeline and tests"
git push origin develop

# No GitHub, ir para Actions tab
# Verificar que pipeline rodou com sucesso
```

---

## 🐳 FASE 6: DOCKER COMPOSE INTEGRATION

### 6.1 Verificar Docker Setup

```bash
# No servidor
docker --version
docker compose version

# Esperado: Docker 20.10+, Compose 2.0+
```

### 6.2 Iniciar Stack Completo

```bash
cd /srv/Projetos/nexus-2.0/docker

# Verificar arquivo
cat docker-compose.yml

# Iniciar todos os serviços
docker compose up -d

# Aguardar healthchecks passarem (~30s)
sleep 30

# Verificar status
docker compose ps

# Esperado:
# nexus-api       Up (healthy)
# nexus-frontend  Up (healthy)
# nexus-postgres  Up (healthy)
# nexus-redis     Up (healthy)
```

### 6.3 Testar Aplicação

```bash
# API deve estar respondendo em http://192.168.0.108:8000
curl -X GET http://localhost:8000/api/health

# Esperado: {"status": "ok"}

# Frontend deve estar em http://192.168.0.108:3000
curl -X GET http://localhost:3000/

# Esperado: HTML da página
```

---

## 📊 PHASE 7: MONITORAMENTO

### 7.1 Verificar Logs

```bash
# Logs da API
docker logs nexus-api -f

# Logs do database
docker logs nexus-postgres -f

# Logs específico
docker logs nexus-api --tail 100 -f
```

### 7.2 Monitoramento de Performance

```bash
# Usar ferramentas disponíveis
docker stats

# Monitorar recursos em tempo real
watch -n 1 "docker stats --no-stream"
```

---

## ✅ CHECKLIST DE VALIDAÇÃO

- [ ] SSH conecta ao servidor
- [ ] Repositório clonado em /srv/Projetos/nexus-2.0
- [ ] Python 3.12+ disponível
- [ ] Virtualenv criado e ativado
- [ ] Dependências instaladas (main + dev)
- [ ] Pytest descobriu ~30+ testes
- [ ] Testes unitários passam ✅
- [ ] Testes integração passam ✅
- [ ] Coverage report gerado (>70%)
- [ ] Linting passa (pylint score 7.0+)
- [ ] Type checking passa (mypy OK)
- [ ] Black formatting aprovado
- [ ] isort imports organizados
- [ ] GitHub Secrets configurados
- [ ] Docker Compose funcionando
- [ ] API respondendo em /api/health
- [ ] GitHub Actions pipeline em verde ✅

---

## 🔧 TROUBLESHOOTING

### Pytest não encontra testes
```bash
# Verificar se __init__.py existe em todos diretórios
find tests/ -type d -exec touch {}/__init__.py \;

# Verificar estrutura
ls -la tests/backend/
```

### Erros de importação
```bash
# Adicionar backend ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/srv/Projetos/nexus-2.0/backend"

# Ou permanentemente no .bashrc
echo 'export PYTHONPATH="${PYTHONPATH}:/srv/Projetos/nexus-2.0/backend"' >> ~/.bashrc
```

### PostgreSQL connection refused
```bash
# Verificar se está rodando
docker ps | grep postgres

# Se não, iniciar
docker compose -f docker/docker-compose.yml up -d postgres

# Testar conexão
psql -h localhost -U postgres -d nexus_test
```

### Redis connection refused
```bash
# Similar ao PostgreSQL
docker compose -f docker/docker-compose.yml up -d redis

# Testar
redis-cli ping
# Esperado: PONG
```

### Permissões negadas
```bash
# Se houver erro de permissão
sudo chown -R kleber:kleber /srv/Projetos

# Ou usar sudo quando necessário
sudo docker ps
```

---

## 📚 PRÓXIMAS ETAPAS

1. ✅ Validar que tudo passou no checklist
2. ⏭️ Começar Fase 2: CI/CD (Semana 4-5)
3. ⏭️ Começar Fase 3: Documentação (Semana 6)
4. ⏭️ Começar Fase 4: IA e Automação

---

## 🆘 SUPORTE

Se algo não funcionar:

1. **Verificar logs**: `docker logs <service>`
2. **Verificar status**: `docker compose ps`
3. **Limpar e recomeçar**: `docker compose down -v && docker compose up -d`
4. **Revisar este guide**
5. **Contactar suporte técnico se necessário**

---

**Bom luck! 🚀 Você está construindo os testes que vão garantir qualidade do Nexus!**
