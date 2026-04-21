# 📖 CONTRIBUTING.md

**Status**: Active Development  
**Last Updated**: Abril 16, 2026

---

## 🎯 Welcome Contributors!

We're building the LAS platform - a comprehensive observability and monitoring solution. We welcome contributions from developers who want to help make enterprise infrastructure monitoring better.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Git
- ~30 minutes

### Setup Local Environment

```bash
# Clone repository
git clone <URL_DO_REPOSITORIO_LAS>
cd las-platform

# Setup backend dev environment
cd backend
python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Setup pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install

# Run tests to verify setup
pytest ../tests/backend -v -k "test_health" --tb=short
```

### Verify Installation

```bash
# Check Python version
python --version  # Must be 3.12+

# Check key tools
black --version
mypy --version
pylint --version

# Run one test
pytest ../tests/backend/unit/test_auth_service.py::TestPasswordHashing::test_hash_password_creates_different_hash -v
```

---

## 📋 Code Style Guide

### Python Code (PEP 8 + Black)

```python
# ✅ GOOD: Clear, type-hinted, well-documented
async def create_agent(
    agent_data: CreateAgentSchema,
    db: AsyncSession,
    tenant_id: str,
) -> AgentResponseSchema:
    """Create new agent in tenant.
    
    Validates agent data, stores in database, and returns created agent.
    
    Args:
        agent_data: Agent creation payload
        db: Database session
        tenant_id: Tenant identifier
    
    Returns:
        Created agent with ID and metadata
    
    Raises:
        HTTPException: If agent name already exists in tenant
    """
    existing = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.name == agent_data.name,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Agent already exists")
    
    agent = Agent(**agent_data.dict(), tenant_id=tenant_id)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    
    return AgentResponseSchema.from_orm(agent)
```

### Type Hints (Mandatory)

```python
# ✅ REQUIRED: All functions must have type hints
def process_data(items: list[str], count: int) -> dict[str, int]:
    return {item: count for item in items}

# ✅ Optional but good for complex types
from typing import Optional, Union, List

def handle_response(
    data: Optional[dict[str, Any]],
    error: Union[str, Exception, None] = None,
) -> tuple[bool, List[str]]:
    ...
```

### Naming Conventions

```python
# Classes: PascalCase
class UserAuthenticationService:
    pass

# Functions & methods: snake_case
async def get_user_by_email(email: str) -> User:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 30

# Private members: _leading_underscore
class Database:
    _connection_pool = None
    
    def _initialize_pool(self):
        pass

# Database tables: snake_case
__tablename__ = "agent_metadata"
```

### Docstrings (Google Style)

```python
def verify_token(token: str, algorithms: list[str]) -> dict[str, Any]:
    """Verify JWT token and extract claims.
    
    Validates token signature, expiration, and claims. Raises
    HTTPException on failure for consistent error handling.
    
    Args:
        token: JWT token string (e.g., "eyJhbGc...")
        algorithms: List of allowed signing algorithms (e.g., ["HS256"])
    
    Returns:
        Dictionary with decoded token claims including "sub", "tenant_id"
    
    Raises:
        HTTPException: Status 401 if token invalid/expired/tampered
        ValueError: If algorithms list is empty
    
    Example:
        >>> claims = verify_token(jwt_token, ["HS256"])
        >>> user_id = claims["sub"]
    """
```

---

## 🌳 Git Workflow

### Branch Naming Convention

```
feature/LAS-123-add-user-authentication  # New feature
bugfix/LAS-456-fix-agent-crash           # Bug fix
docs/update-deployment-guide               # Documentation
test/increase-auth-coverage                # Tests
chore/upgrade-dependencies                 # Maintenance
refactor/simplify-gateway-routing          # Refactoring
```

**Format**: `{type}/{ticket-number}-{short-description}`
- Use lowercase
- Use hyphens (not underscores)
- Reference ticket number if applicable

### Commit Messages (Conventional Commits)

```
# Format
<type>(<scope>): <subject>

<body>

<footer>

# Examples

feat(auth): implement JWT token refresh mechanism
- Add refresh token generation
- Store refresh tokens in Redis
- Implement token rotation

fix(agents): handle null agent_id in bootstrap
Prevent NullPointerException when agent_id missing from request.
Fixes #123

docs(deployment): update HA configuration guide
Add Redis Sentinel configuration examples for production.

test(auth): increase login endpoint coverage to 95%

chore(deps): upgrade FastAPI to 0.100.0
Security and performance improvements.
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Test improvements
- `chore`: Maintenance, dependencies
- `refactor`: Code reorganization
- `perf`: Performance improvements
- `security`: Security fixes

**Guidelines:**
- ✅ Present tense ("add" not "added")
- ✅ Lowercase first letter
- ✅ No period at end of subject
- ✅ Max 50 chars for subject
- ✅ Reference issues in body (#123)

---

## 🧪 Testing Requirements

### Before Commit

```bash
# Run tests for your changes
pytest tests/backend/unit/test_your_feature.py -v

# Run full test suite
pytest tests/backend -v

# Check coverage
pytest tests/backend --cov=app --cov-report=term
# Ensure coverage doesn't decrease

# Code quality checks
black app
isort app
mypy app --ignore-missing-imports
pylint app --disable=R,C --fail-under=7.0
```

### Test Patterns

Always write tests for:
1. ✅ Happy path (normal operation)
2. ✅ Edge cases (boundary conditions)
3. ✅ Error cases (exceptions/validation)
4. ✅ Integration (components working together)

```python
@pytest.mark.unit
class TestUserCreation:
    """Test user creation scenarios"""
    
    def test_create_user_success(self):
        """Test successful user creation"""
        # Setup
        user_data = {"email": "test@example.com", "password": "Secure123!"}
        
        # Execute
        user = create_user(**user_data)
        
        # Assert
        assert user.email == user_data["email"]
        assert user.is_active is True
    
    def test_create_user_invalid_email(self):
        """Test creation with invalid email"""
        with pytest.raises(ValidationError):
            create_user(email="not-an-email", password="Secure123!")
    
    def test_create_user_duplicate_raises_error(self):
        """Test duplicate user raises proper error"""
        create_user(email="test@example.com", password="Secure123!")
        
        with pytest.raises(HTTPException) as exc_info:
            create_user(email="test@example.com", password="Secure123!")
        
        assert exc_info.value.status_code == 409
```

---

## 📝 Pull Request Process

### 1. Create Feature Branch

```bash
git checkout -b feature/LAS-789-new-feature
```

### 2. Make Changes

```bash
# Edit code, add tests, update docs
# Run tests frequently to catch issues early
pytest tests/backend -v
```

### 3. Commit Changes

```bash
git add app/services/new_feature.py tests/backend/unit/test_new_feature.py
git commit -m "feat(services): add new feature implementation

- Implement core logic
- Add error handling
- Add documentation"
```

### 4. Push to GitHub

```bash
git push origin feature/LAS-789-new-feature
```

### 5. Create Pull Request

- Go to GitHub repository
- Click "Compare & pull request"
- Fill PR template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing
- [ ] Coverage maintained or improved

## Checklist
- [ ] Code follows PEP 8 style guide
- [ ] Type hints added
- [ ] Docstrings added
- [ ] Tests added
- [ ] Documentation updated
- [ ] No hardcoded secrets/credentials
```

### 6. Code Review

Our team will review:
- ✅ Code quality & style
- ✅ Test coverage
- ✅ Documentation
- ✅ Security implications
- ✅ Performance impact

### 7. Merge

Once approved and tests pass:
```bash
# This happens automatically on GitHub
```

---

## 🔍 Code Review Checklist

**Before requesting review, verify:**

- [ ] **Tests**
  - [ ] All tests passing locally
  - [ ] New tests for new functionality
  - [ ] No test regressions
  - [ ] Coverage maintained (80%+)

- [ ] **Code Quality**
  - [ ] PEP 8 compliant
  - [ ] Type hints present
  - [ ] Docstrings added
  - [ ] No hardcoded values
  - [ ] No unused imports

- [ ] **Security**
  - [ ] No secrets in code
  - [ ] Input validation present
  - [ ] SQL injection prevention
  - [ ] Auth checks on protected endpoints

- [ ] **Documentation**
  - [ ] Comments for complex logic
  - [ ] README updated if needed
  - [ ] API docs updated
  - [ ] Changelog entry added

- [ ] **Performance**
  - [ ] No N+1 database queries
  - [ ] Async/await used properly
  - [ ] No blocking operations
  - [ ] Cache utilized where appropriate

---

## 🏗️ Architecture Guidelines

### Layered Architecture

```
FastAPI Endpoints (Routers)
         ↓
    Services (Business Logic)
         ↓
    Models (ORM/Database)
         ↓
    Database (PostgreSQL)
```

Follow this pattern:

```python
# ❌ BAD: DB logic in endpoint
@router.post("/agents")
async def create_agent(data: CreateAgentSchema, db: AsyncSession):
    result = await db.execute(
        insert(Agent).values(**data.dict())
    )
    await db.commit()
    return result

# ✅ GOOD: Separation of concerns
@router.post("/agents")
async def create_agent(
    data: CreateAgentSchema,
    agent_service: AgentService = Depends(),
):
    return await agent_service.create(data)

# In services/agent_service.py
class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: CreateAgentSchema) -> Agent:
        agent = Agent(**data.dict())
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent
```

---

## 🚫 Common Mistakes to Avoid

### ❌ DON'T

```python
# ❌ No type hints
def get_user(email):
    return db.query(User).filter(email=email).first()

# ❌ Hardcoded values
PASSWORD = "admin123"

# ❌ Print debugging
print(f"User: {user}")

# ❌ Bare exceptions
try:
    dangerous_operation()
except:
    pass

# ❌ SQL injection
query = f"SELECT * FROM users WHERE email='{email}'"

# ❌ No error handling
response = requests.get(url)
return response.json()
```

### ✅ DO

```python
# ✅ Type hints always
async def get_user(email: str) -> Optional[User]:
    return await db.execute(
        select(User).where(User.email == email)
    )

# ✅ Environment variables
PASSWORD = os.getenv("DB_PASSWORD")

# ✅ Proper logging
logger.info(f"User login: {user.id}")

# ✅ Specific exceptions
try:
    dangerous_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    raise

# ✅ Parameterized queries (ORM does this)
return await db.execute(
    select(User).where(User.email == email)
)

# ✅ Error handling
try:
    response = await httpx.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
except httpx.HTTPError as e:
    logger.error(f"Request failed: {e}")
    raise
```

---

## 📚 Development Tools & IDE Setup

### VS Code Extensions

Recommended:
- Python (Microsoft)
- Pylance
- Black Formatter
- isort
- Prettier
- GitLens
- Pytest Runner

### IDE Configuration

**.vscode/settings.json:**
```json
{
    "python.linting.pylintEnabled": true,
    "python.linting.pylintPath": "pylint",
    "python.linting.pylintArgs": ["--disable=R,C"],
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["-l 100"],
    "[python]": {
        "editor.defaultFormatter": "ms-python.python",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll": true
        }
    },
    "isort.args": ["--profile", "black", "--line-length", "100"]
}
```

---

## 🆘 Getting Help

- 📖 Check documentation in `/docs`
- 🧪 Review existing tests for patterns
- 💬 Ask in pull request comments
- 🐛 Report bugs in Issues
- 🔗 Check related PRs for context

---

## ✨ Recognition

Contributors with 5+ merged PRs become:
- GitHub repository maintainers
- Visible in CONTRIBUTORS.md
- Featured in releases

---

## 📜 License

All contributions are made under the MIT License.

---

**Thanks for contributing to LAS! 🚀**
