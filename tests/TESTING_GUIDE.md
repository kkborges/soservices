# ðŸ§ª Testing Guide - LAS Platform

**Status**: Ready for implementation  
**Date**: April 2026  
**Coverage Target**: 80%+ (Enforce via CI)

---

## ðŸ“‹ Quick Start

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Run all tests
pytest tests/backend -v

# 3. Run with coverage report
pytest tests/backend -v --cov=app --cov-report=html

# 4. Run specific test
pytest tests/backend/unit/test_auth_service.py::TestPasswordHashing -v

# 5. Run tests in parallel (faster)
pytest tests/backend -n auto
```

---

## ðŸ—ï¸ Test Structure

```
tests/backend/
â”œâ”€â”€ conftest.py                 # Shared fixtures & configuration
â”œâ”€â”€ unit/
â”‚   â”œâ”€â”€ test_auth_service.py   # Auth logic tests
â”‚   â”œâ”€â”€ test_schemas.py        # Pydantic validation tests
â”‚   â””â”€â”€ test_*.py              # Other service tests
â”œâ”€â”€ integration/
â”‚   â”œâ”€â”€ test_main_endpoints.py # Main API endpoints
â”‚   â”œâ”€â”€ test_auth_endpoints.py # Auth flow tests
â”‚   â””â”€â”€ test_*.py              # DB, cache integration
â”œâ”€â”€ e2e/
â”‚   â”œâ”€â”€ test_user_flow.py      # Complete user journey
â”‚   â””â”€â”€ test_agent_registration.py # Agent bootstrap flow
â”œâ”€â”€ fixtures/
â”‚   â”œâ”€â”€ db.py                  # Database fixtures
â”‚   â””â”€â”€ models.py              # Pre-built model instances
â””â”€â”€ mocks/
    â”œâ”€â”€ cloud_providers.py     # AWS/Azure/GCP mocks
    â””â”€â”€ external_apis.py       # OpenAI, Anthropic mocks
```

---

## ðŸ§© Test Categories

### 1. **Unit Tests** (`tests/backend/unit/`)
- No external dependencies
- Fast execution (< 1 sec each)
- Test single functions/methods
- Mock all external services

```bash
pytest tests/backend/unit -v -m unit
```

**Examples:**
- Password hashing
- Token creation/validation
- Schema validation
- Utility functions

### 2. **Integration Tests** (`tests/backend/integration/`)
- Requires services (DB, Redis, etc)
- Slower but comprehensive
- Test multiple components together
- Real database/cache

```bash
pytest tests/backend/integration -v -m integration
```

**Examples:**
- Endpoint authentication
- Database CRUD operations
- Gateway routing
- Cache operations

### 3. **End-to-End Tests** (`tests/backend/e2e/`)
- Complete user flows
- Slowest but most realistic
- Test full system behavior

```bash
pytest tests/backend/e2e -v -m e2e
```

**Examples:**
- User registration â†’ Login â†’ Create agent
- Agent bootstrap â†’ Send data â†’ View in dashboard

---

## ðŸ“š Available Fixtures

### Database
```python
@pytest.fixture
async def db_session_test():
    """In-memory SQLite for async tests"""

@pytest.fixture
def db_session_sync():
    """In-memory SQLite for sync tests"""
```

### Authentication
```python
@pytest.fixture
def valid_jwt_token():
    """Valid JWT token for authorized requests"""

@pytest.fixture
def expired_jwt_token():
    """Expired JWT token for negative tests"""

@pytest.fixture
def auth_headers():
    """Authorization headers with valid token"""
```

### HTTP Clients
```python
@pytest.fixture
async def async_client():
    """AsyncClient for testing async endpoints"""

@pytest.fixture
def sync_client():
    """TestClient for testing sync endpoints"""
```

### Mocks
```python
@pytest.fixture
def mock_redis():
    """Mock Redis operations"""

@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls"""

@pytest.fixture
def mock_aws_s3():
    """Mock AWS S3 operations"""
```

### Sample Data
```python
@pytest.fixture
def sample_user_data():
    """Pre-built user object"""

@pytest.fixture
def sample_agent_data():
    """Pre-built agent object"""

@pytest.fixture
def sample_alert_data():
    """Pre-built alert object"""
```

---

## ðŸ” Running Tests

### Run Everything
```bash
pytest tests/backend
```

### Run Specific Category
```bash
pytest tests/backend -m unit              # Unit tests only
pytest tests/backend -m integration       # Integration only
pytest tests/backend -m "not slow"        # Exclude slow tests
```

### Run with Coverage
```bash
# Coverage report on terminal
pytest tests/backend --cov=app --cov-report=term

# HTML coverage report (open coverage_html/index.html)
pytest tests/backend --cov=app --cov-report=html

# XML report (for CI)
pytest tests/backend --cov=app --cov-report=xml
```

### Run in Parallel
```bash
# Significantly faster for large test suites
pytest tests/backend -n auto
```

### Run with Debugging
```bash
# Drop into debugger on failure
pytest tests/backend --pdb

# Show print statements
pytest tests/backend -s

# Verbose output with timings
pytest tests/backend -v --durations=10
```

---

## âœï¸ Writing Tests

### Unit Test Example
```python
@pytest.mark.unit
class TestAuthService:
    def test_hash_password(self):
        """Test password hashing is secure"""
        from app.services.auth_service import get_password_hash
        
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert hashed.startswith("$2b$")
```

### Integration Test Example
```python
@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_login_success(self, async_client, auth_headers):
        """Test successful login"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "user@example.com",
                "password": "Password123!"
            }
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()
```

### Test with Fixtures
```python
def test_create_user(db_session_sync, sample_user_data):
    """Test user creation"""
    from app.models import User
    
    user = User(**sample_user_data)
    db_session_sync.add(user)
    db_session_sync.commit()
    
    queried = db_session_sync.query(User).filter_by(
        id=sample_user_data["id"]
    ).first()
    
    assert queried is not None
    assert queried.email == sample_user_data["email"]
```

---

## ðŸ”§ Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Setup hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

**.pre-commit-config.yaml:**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
  
  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

---

## ðŸ“Š Coverage Report

After running:
```bash
pytest tests/backend --cov=app --cov-report=html
```

Open `coverage_html/index.html` in browser to see:
- Line coverage by file
- Uncovered lines highlighted
- Missing branches
- Coverage percentage

**Target Metrics:**
- Overall: 80%+
- Auth module: 95%+
- Critical paths: 100%

---

## ðŸš€ CI/CD Integration

GitHub Actions runs tests automatically on:
- Push to main/develop
- Pull requests

See `.github/workflows/ci-cd.yml` for configuration.

**Status**: âœ… Tests must pass before merge

---

## ðŸ› Debugging Failed Tests

### 1. Run with verbose output
```bash
pytest tests/backend/test_file.py::test_name -vv -s
```

### 2. Drop into debugger on failure
```bash
pytest tests/backend --pdb
```

### 3. Set breakpoints
```python
import pdb; pdb.set_trace()
```

### 4. Use IPython for debugging
```bash
pip install ipdb
# In test: import ipdb; ipdb.set_trace()
```

---

## ðŸ“ˆ Coverage by Module

| Module | Current | Target | Status |
|--------|---------|--------|--------|
| auth_service | 0% | 95% | ðŸ”´ |
| agent_service | 0% | 85% | ðŸ”´ |
| gateway_routing | 0% | 80% | ðŸ”´ |
| models | 0% | 80% | ðŸ”´ |
| schemas | 0% | 75% | ðŸ”´ |

---

## âœ… Checklist for New Tests

Before committing:
- [ ] Tests have clear names (describe what they test)
- [ ] Tests are marked with `@pytest.mark.unit/integration/e2e`
- [ ] Tests use fixtures instead of setup/teardown
- [ ] Mock external dependencies
- [ ] Assertions are specific (not just `assert True`)
- [ ] Tests are independent (can run in any order)
- [ ] Error cases tested (not just happy path)
- [ ] No hardcoded credentials
- [ ] No prints (use `logging` or `-s` flag)

---

## ðŸ”— Related Documents

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Code contribution guidelines
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - System architecture
- [DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Local development setup
- [CI/CD Pipeline](.github/workflows/ci-cd.yml) - GitHub Actions config

---

## ðŸ“ž Support

Questions about tests?
1. Check existing test examples
2. Review pytest documentation
3. Ask in code review

**Happy testing! ðŸš€**

