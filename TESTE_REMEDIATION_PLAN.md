# 🔧 Test Remediation Plan - Phase 0

**Date**: April 16, 2026  
**Status**: Foundation Tests Implementation  
**Goal**: Adapt test suite to match actual codebase structure

---

## ✅ **What Was Fixed**

### 1. JWT Token Functions (`auth_service.py`)
✅ **Added**:
- `create_access_token()` - Creates JWT tokens with configurable expiration
- `decode_token()` - Validates and decodes JWT tokens

```python
# Now available for tests
token = create_access_token(
    data={"sub": "user-123", "tenant_id": "tenant-456"},
    expires_delta=timedelta(hours=1)
)
```

### 2. Async Client Fixture (`conftest.py`)
✅ **Fixed**:
- `async_client` fixture now returns proper `AsyncClient` instead of async_generator
- Can be used directly in tests: `response = await async_client.get("/api")`

---

## 🔴 **Remaining Issues**

### 1. Missing `app/schemas/` Directory
**Problem**: 
- Tests expect Pydantic validation models in `app/schemas/`
- Directory exists but is **empty**

**Impact**: 12 tests fail with `ModuleNotFoundError`

**Status**: ⏳ Needs implementation

### 2. API Validation Layer
**Current State**:
- Validation happens at **ORM level** (SQLAlchemy models)
- No request/response Pydantic schemas

**Solution Options**:
- **Option A** (Quick): Disable schema tests for now, mock them later
- **Option B** (Proper): Create Pydantic schemas aligning with models
- **Option C** (Hybrid): Create minimal schemas with `@skip` markers

---

## 📋 **Test Execution Plan**

### **Phase 0: Foundation (TODAY)**
✅ Implement missing JWT functions  
✅ Fix async_client fixture  
⏳ Update test suite to work with real code

### **Phase 1: Passing Tests (Next)**
- Unit tests for `auth_service` → Should PASS with new functions
- Integration tests with real API endpoints
- Mock missing schemas

### **Phase 2: Security Tests**
- Token expiration validation
- Unauthorized endpoint protection
- CORS and security headers

### **Phase 3: Full Coverage**
- Complete schemas implementation
- E2E tests
- Performance testing

---

## 🚀 **Next Steps On Server**

### **Step 1: Pull Latest Changes**
```bash
cd /srv/Projetos/nexus-2.0
git pull origin develop
```

### **Step 2: Run Tests (Will Still Fail on Schemas)**
```bash
# These will now pass:
./scripts/run_tests.sh tests/backend/unit/test_auth_service.py -v

# These will still fail (expected):
./scripts/run_tests.sh tests/backend/unit/test_schemas.py -v
```

### **Step 3: Disable Schema Tests Temporarily**
```bash
# Option A: Skip them
pytest tests/backend/unit -v -k "not Schema"

# Option B: Run only passing tests
pytest tests/backend/unit/test_auth_service.py -v --cov=app
```

### **Step 4: Generate Coverage Report**
```bash
cd /srv/Projetos/nexus-2.0
./scripts/run_tests.sh tests/backend/ -v --cov=app --cov-report=html

# View report
firefox backend/coverage_html/index.html
```

---

## 📊 **Expected Test Status**

### Current (Before Fixes)
```
FAILED:  36 tests
ERRORS:  4 tests
STATUS:  Coverage 0.48%
```

### After JWT Fix (Partially)
```
PASSED:  ~8 tests (auth_service.py functions)
FAILED:  ~20 tests (still missing schemas)
ERRORS:  ~0 errors (fixtures fixed)
STATUS:  Coverage ~2-3%
```

### After Schema Implementation (Goal)
```
PASSED:  ~40+ tests
FAILED:  0 tests
ERRORS:  0 errors
STATUS:  Coverage 70%+
```

---

## 🛠️ **Schemas Implementation** (When Ready)

Create minimal Pydantic models matching ORM:

```python
# app/schemas/__init__.py
from .auth import LoginSchema, TokenResponse
from .agent import AgentSchema
from .common import PaginationParams

__all__ = ["LoginSchema", "TokenResponse", "AgentSchema", "PaginationParams"]
```

```python
# app/schemas/auth.py
from pydantic import BaseModel, EmailStr

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
```

---

## 🎯 **Success Criteria**

- ✅ `create_access_token()` works and generates valid JWT
- ✅ `async_client` fixture returns usable HTTP client
- ✅ Unit tests for auth functions pass
- ✅ Coverage gradually increases (aim for 50%+ by end of phase)
- ✅ CI/CD pipeline shows green for passing tests

---

## 📞 **Support**

If tests still fail after pulling:

```bash
# Check JWT implementation
cd /srv/Projetos/nexus-2.0/backend
python3 -c "from app.services.auth_service import create_access_token; print(create_access_token({'sub': 'test'}))"

# Check fixture
cd /srv/Projetos/nexus-2.0
./scripts/run_tests.sh --fixtures | grep async_client

# Run single passing test
./scripts/run_tests.sh tests/backend/unit/test_auth_service.py::TestPasswordHashing::test_verify_password_success -v
```

---

**Next**: After these pass, implement `app/schemas/` for ~25% more test coverage 🚀
