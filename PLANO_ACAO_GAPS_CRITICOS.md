# 🚀 PLANO DE AÇÃO - RESOLVER GAPS CRÍTICOS

**Status**: Ready for execution  
**Data**: Abril 16, 2026  
**Ambiente**: nexus-2.0 em 192.168.0.108:/srv/Projetos

---

## 📋 RESUMO EXECUTIVO

**Objetivo**: Resolver 3 gaps críticos que bloqueiam escalabilidade:

| Gap | Score Atual | Score Alvo | Esforço | Timeline |
|-----|-------------|-----------|---------|----------|
| Testes | 1/10 | 8/10 | 2-3 sprints | 3 semanas |
| CI/CD | 2/10 | 9/10 | 1-2 sprints | 2 semanas |
| Documentação | 5/10 | 9/10 | 1 sprint | 1 semana |
| **Total** | - | - | **4-6 sprints** | **6 semanas** |

---

## 🎯 FASE 1: TESTES AUTOMATIZADOS (Semana 1-3)

### 1.1 Estrutura Inicial

```
tests/
├── backend/
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures e configuração
│   ├── unit/
│   │   ├── test_auth_service.py    # Testes de autenticação
│   │   ├── test_mtls_service.py    # Testes de mTLS
│   │   ├── test_models.py          # Validações ORM
│   │   └── test_schemas.py         # Validações Pydantic
│   ├── integration/
│   │   ├── test_auth_endpoints.py  # Tests de endpoints /auth
│   │   ├── test_agents_endpoints.py # Tests de agents CRUD
│   │   ├── test_gateway_routing.py # Tests de routing
│   │   └── test_database.py        # DB migrations, constraints
│   ├── e2e/
│   │   ├── test_user_flow.py       # Complete user journey
│   │   └── test_agent_registration.py # Agent bootstrap flow
│   ├── fixtures/
│   │   ├── db.py                   # Database fixtures
│   │   ├── auth.py                 # Auth token fixtures
│   │   ├── mtls.py                 # mTLS cert fixtures
│   │   └── models.py               # Pre-populated models
│   └── mocks/
│       ├── cloud_providers.py      # AWS/Azure/GCP mocks
│       └── external_apis.py        # OpenAI, external APIs
├── frontend/
│   └── (future: Cypress/Playwright)
└── e2e/
    └── (future: Full stack tests)
```

### 1.2 Ferramentas e Dependências

```toml
[tool.pytest.ini_options]
testpaths = ["tests/backend"]
python_files = ["test_*.py"]
addopts = "-v --cov=app --cov-report=html --cov-report=term"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow running tests",
]

[tool.coverage.run]
branch = true
omit = [
    "*/tests/*",
    "*/migrations/*",
    "app/main.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

**Dependências a adicionar em `backend/requirements-dev.txt`:**

```
pytest==7.4.4
pytest-asyncio==0.24.0        # Para testes async
pytest-cov==4.1.0             # Coverage reports
pytest-mock==3.14.0           # Mock fixtures
pytest-xdist==3.6.1           # Parallel test execution
factory-boy==3.3.0            # Model factories
faker==23.2.0                 # Generate fake data
freezegun==1.4.0              # Mock datetime
httpx==0.28.1                 # Async HTTP client
```

### 1.3 Exemplo de Fixture (conftest.py)

```python
# tests/backend/conftest.py
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.core.config import settings

# Override settings para testes
@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes async"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db_url():
    """Database em memória para testes"""
    return "sqlite:///:memory:"

@pytest.fixture
def db_session(test_db_url):
    """Sessão de DB isolada por teste"""
    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def redis_mock(mocker):
    """Mock Redis para testes"""
    mock = mocker.AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    return mock

@pytest.fixture
async def async_client():
    """Cliente HTTP assíncrono para testes"""
    from httpx import AsyncClient
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def valid_token(db_session):
    """Gera JWT válido para testes"""
    from app.services.auth_service import create_access_token
    
    token = create_access_token(
        data={"sub": "test-user-id", "tenant_id": "test-tenant"},
        expires_delta=timedelta(hours=1)
    )
    return token
```

### 1.4 Exemplo de Teste Unitário

```python
# tests/backend/unit/test_auth_service.py
import pytest
from datetime import timedelta
from app.services.auth_service import (
    verify_password,
    get_password_hash,
    decode_token,
    create_access_token,
)

class TestAuthService:
    """Testes do serviço de autenticação"""
    
    def test_hash_password(self):
        """Verifica se senha é hasheada corretamente"""
        plain_password = "SecurePass123!"
        hashed = get_password_hash(plain_password)
        
        # Hash não deve ser igual ao plain text
        assert hashed != plain_password
        
        # Verify deve reconhecer a senha
        assert verify_password(plain_password, hashed) is True
        assert verify_password("WrongPass", hashed) is False
    
    def test_create_and_decode_token(self):
        """Verifica ciclo completo de token JWT"""
        data = {"sub": "user-123", "tenant_id": "tenant-456"}
        token = create_access_token(data, expires_delta=timedelta(hours=1))
        
        # Token não deve estar vazio
        assert token
        assert token.startswith("nxa_")  # Agent token prefix
        
        # Decode deve retornar dados originais
        decoded = decode_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["tenant_id"] == "tenant-456"
    
    def test_expired_token(self):
        """Verifica rejeição de token expirado"""
        data = {"sub": "user-123"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        
        assert exc_info.value.status_code == 401
```

### 1.5 Exemplo de Teste de Integração

```python
# tests/backend/integration/test_auth_endpoints.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
class TestAuthEndpoints:
    """Testes dos endpoints de autenticação"""
    
    async def test_login_success(self, async_client: AsyncClient, db_session):
        """Testa login bem-sucedido"""
        # Setup: criar usuário no DB
        user = await create_test_user(db_session, 
            email="test@soservices.com.br",
            password="TestPass123!"
        )
        
        # Action: fazer login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@soservices.com.br",
                "password": "TestPass123!"
            }
        )
        
        # Assert: verificar resposta
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@soservices.com.br"
    
    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        """Testa login com credenciais inválidas"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@soservices.com.br",
                "password": "WrongPass"
            }
        )
        
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()
    
    async def test_list_agents_requires_auth(self, async_client: AsyncClient):
        """Testa proteção de endpoint com autenticação"""
        response = await async_client.get("/api/v1/agents")
        
        assert response.status_code == 401
        
        # Com token válido deve funcionar
        response = await async_client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 200
```

### 1.6 Coverage Target

- **Alvo Mínimo**: 80% coverage
- **Crítico**: 95% em auth, mTLS, payment flows
- **CI bloqueará**: PRs que reduzem coverage

**Fase 1 Timeline:**
- Semana 1: Setup infra de testes + 20 testes base
- Semana 2: 50 testes unitários adicionais
- Semana 3: 30 testes integração + 10 e2e

---

## 🔄 FASE 2: CI/CD PIPELINE (Semana 4-5)

### 2.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/nexus-api

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    name: Lint & Test
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: nexus_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
          cache: "pip"
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install -r backend/requirements-dev.txt
      
      - name: Lint with pylint
        run: |
          pylint backend/app --disable=R,C --fail-under=8.0
      
      - name: Type check with mypy
        run: |
          mypy backend/app --ignore-missing-imports
      
      - name: Format check with black
        run: |
          black --check backend/app
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:test@localhost/nexus_test
          REDIS_URL: redis://localhost:6379
          TESTING: "true"
        run: |
          pytest tests/backend -v --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: true
  
  build-and-push:
    needs: lint-and-test
    runs-on: ubuntu-latest
    name: Build Docker Image
    permissions:
      contents: read
      packages: write
    
    if: github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: ./backend
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
  
  deploy-dev:
    needs: build-and-push
    runs-on: ubuntu-latest
    name: Deploy to Dev
    if: github.ref == 'refs/heads/develop'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to dev server
        env:
          DEV_HOST: ${{ secrets.DEV_HOST }}
          DEV_USER: ${{ secrets.DEV_USER }}
          DEV_SSH_KEY: ${{ secrets.DEV_SSH_KEY }}
        run: |
          mkdir -p ~/.ssh
          echo "$DEV_SSH_KEY" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          
          ssh -o StrictHostKeyChecking=no $DEV_USER@$DEV_HOST \
            "cd /srv/Projetos/nexus-2.0 && ./deploy-dev.sh"
  
  deploy-prod:
    needs: build-and-push
    runs-on: ubuntu-latest
    name: Deploy to Production
    if: github.ref == 'refs/heads/main'
    
    environment:
      name: production
      url: https://api.soservices.com.br
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Request approval
        run: echo "Deployment requires manual approval in GitHub"
      
      - name: Deploy to prod server
        env:
          PROD_HOST: ${{ secrets.PROD_HOST }}
          PROD_USER: ${{ secrets.PROD_USER }}
          PROD_SSH_KEY: ${{ secrets.PROD_SSH_KEY }}
        run: |
          mkdir -p ~/.ssh
          echo "$PROD_SSH_KEY" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          
          ssh -o StrictHostKeyChecking=no $PROD_USER@$PROD_HOST \
            "cd /srv/Projetos/nexus && ./deploy-prod.sh"
```

### 2.2 Configuração Local (pylintrc, pyproject.toml)

```toml
# backend/pyproject.toml
[tool.black]
line-length = 100
target-version = ['py312']
include = '\.pyi?$'

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Gradual typing
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true

[tool.pylint.messages_control]
disable = [
    "C0111",  # missing-docstring
    "R0903",  # too-few-public-methods
    "R0913",  # too-many-arguments
]

[tool.pylint.format]
max-line-length = 100
```

### 2.3 Deploy Scripts

```bash
#!/bin/bash
# deploy-dev.sh

set -e

echo "🚀 Deploying to development..."

# Pull latest
git pull origin develop

# Build image
docker build -t nexus-api:dev ./backend

# Stop old container
docker stop nexus-api-dev || true
docker rm nexus-api-dev || true

# Start new container
docker run -d \
  --name nexus-api-dev \
  --network nexus-network \
  -p 8000:8000 \
  -e DATABASE_URL=$DEV_DB_URL \
  -e REDIS_URL=$DEV_REDIS_URL \
  nexus-api:dev

echo "✅ Development deployed successfully"
docker logs -f nexus-api-dev
```

**Fase 2 Timeline:**
- Dia 1-2: Setup GitHub Actions
- Dia 3-4: Linting + Type checking
- Dia 5-6: Build & push Docker
- Dia 7-10: Deploy automation

---

## 📚 FASE 3: DOCUMENTAÇÃO (Semana 6)

### 3.1 CONTRIBUTING.md

```markdown
# CONTRIBUTING

## Setup Local

### Requisitos
- Python 3.12+
- Docker + Docker Compose
- Git

### Instalação

\`\`\`bash
# Clone repo
git clone https://github.com/soservices/nexus.git
cd nexus

# Backend dev env
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend dev env
cd ../frontend
npm install
npm run dev
\`\`\`

## Padrões de Código

### Naming
- Classes: PascalCase
- Functions: snake_case
- Constants: UPPER_SNAKE_CASE
- Private: _leading_underscore

### Type Hints (Obrigatório)
\`\`\`python
async def create_agent(
    agent_data: CreateAgentSchema,
    tenant_id: str,
    db: AsyncSession
) -> AgentResponseSchema:
    ...
\`\`\`

### Docstrings (Google style)
\`\`\`python
def verify_token(token: str) -> dict:
    \"\"\"Verify JWT token validity.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    \"\"\"
\`\`\`

## Commits (Conventional Commits)

\`\`\`
feat(auth): add rate limiting to login endpoint
fix(agents): handle null tenant_id in bootstrap
docs(deployment): update HA configuration
test(auth): add token expiry tests
chore(deps): upgrade FastAPI to 0.100.0
\`\`\`

## Pull Requests

1. Create branch: `git checkout -b feature/NEXUS-123-description`
2. Make changes
3. Run tests: `pytest tests/backend -v`
4. Run linters: `black . && pylint app && mypy app`
5. Push: `git push origin feature/...`
6. Create PR (use template)

## Testing

\`\`\`bash
# Run all tests
pytest tests/backend -v

# Run specific test
pytest tests/backend/unit/test_auth_service.py::test_hash_password -v

# With coverage
pytest tests/backend --cov=app --cov-report=html

# Parallel execution (faster)
pytest tests/backend -n auto
\`\`\`

## Code Review Checklist

- [ ] Tests cover happy path + edge cases
- [ ] No hardcoded values (use env vars)
- [ ] Type hints present
- [ ] Error messages are clear
- [ ] No console.log/print statements
- [ ] No secrets in code
\`\`\`

### 3.2 ARCHITECTURE.md (já iniciado)

Será expandido com:
- Diagrama de fluxo de requisição
- Padrão MVC/Service Layer
- Decision log (ADR)
- Padrões e anti-patterns

### 3.3 DEVELOPMENT.md

Quickstart, debugging, troubleshooting

---

## ✅ CHECKLIST DE EXECUÇÃO

### Pre-requisitos
- [ ] Acesso SSH/SCP confirmado (192.168.0.108)
- [ ] Docker e Docker Compose no servidor
- [ ] Git configurado
- [ ] Repositório privado no GitHub

### Fase 1: Testes
- [ ] Estrutura de testes criada
- [ ] 20 testes base implementados
- [ ] Coverage reporting configurado
- [ ] Fixtures e mocks prontos

### Fase 2: CI/CD
- [ ] GitHub Actions workflow criado
- [ ] Linting (pylint, black, isort) funcional
- [ ] Type checking (mypy) configurado
- [ ] Docker build automatizado
- [ ] Deploy scripts testados

### Fase 3: Documentação
- [ ] CONTRIBUTING.md completo
- [ ] ARCHITECTURE.md expandido
- [ ] DEVELOPMENT.md criado
- [ ] Docstrings adicionadas a models/services

---

## 📊 MÉTRICAS DE SUCESSO

| Métrica | Target | Como Medir |
|---------|--------|-----------|
| Test Coverage | 80%+ | `pytest --cov-report=term` |
| Linting Score | 8.5/10 | `pylint app` |
| Type Checking | 100% | `mypy app` |
| CI Pass Rate | 95%+ | GitHub Actions dashboard |
| Deploy Time | <5 min | Release notes |

---

## 🎯 PRÓXIMOS PASSOS

1. **Você revisar este plano** ✅
2. **Eu configurar ambiente em nexus-2.0** (servidor)
3. **Implementar Fase 1** (testes)
4. **Implementar Fase 2** (CI/CD)
5. **Implementar Fase 3** (docs)
6. **Validação e ajustes**

---

**Aguardando confirmação para iniciar! Pronto? 🚀**
