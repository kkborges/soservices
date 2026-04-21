"""
Main pytest configuration and shared fixtures for backend tests
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import Generator, AsyncGenerator
from datetime import datetime, timedelta, timezone

# Test environment setup
os.environ["TESTING"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-12345678901234567890"
os.environ["ALGORITHM"] = "HS256"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Setup mock environment variables"""
    env_vars = {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-123456789012345678",
        "APP_NAME": "LAS Test",
        "APP_VERSION": "3.0.0-test",
        "DEBUG": "true",
        "MTLS_ENABLED": "false",
        "MTLS_REQUIRED": "false",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


# === Database Fixtures ===

@pytest_asyncio.fixture
async def db_session_test():
    """Provide test database session"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    import app.models  # noqa: F401 - ensure all ORM tables are registered
    
    # Use SQLite in-memory for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_async(db_session_test):
    """Backward-compatible async database session fixture."""
    yield db_session_test


@pytest.fixture
def db_session_sync():
    """Provide synchronous test database session (if needed)"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


# === Authentication Fixtures ===

@pytest.fixture
def sample_user_data():
    """Provide sample user data for tests"""
    return {
        "id": "user-test-123",
        "email": "test@soservices.com.br",
        "tenant_id": "tenant-test-123",
        "username": "testuser",
        "is_active": True,
        "is_admin": False,
    }


@pytest.fixture
def sample_admin_data():
    """Provide sample admin user data"""
    return {
        "id": "admin-test-123",
        "email": "admin@soservices.com.br",
        "tenant_id": "platform-admin",
        "username": "testadmin",
        "is_active": True,
        "is_admin": True,
    }


@pytest.fixture
def valid_jwt_token(sample_user_data):
    """Generate valid JWT token for tests"""
    from app.services.auth_service import create_access_token
    from datetime import timedelta
    
    token = create_access_token(
        data={
            "sub": sample_user_data["id"],
            "tenant_id": sample_user_data["tenant_id"],
        },
        expires_delta=timedelta(hours=1),
    )
    return token


@pytest.fixture
def expired_jwt_token(sample_user_data):
    """Generate expired JWT token for tests"""
    from app.services.auth_service import create_access_token
    from datetime import timedelta
    
    token = create_access_token(
        data={
            "sub": sample_user_data["id"],
            "tenant_id": sample_user_data["tenant_id"],
        },
        expires_delta=timedelta(seconds=-1),  # Already expired
    )
    return token


@pytest.fixture
def auth_headers(valid_jwt_token):
    """Provide authorization headers with valid token"""
    return {
        "Authorization": f"Bearer {valid_jwt_token}",
        "Content-Type": "application/json",
    }


# === HTTP Client Fixtures ===

@pytest_asyncio.fixture
async def async_client(db_session_async):
    """Provide async HTTP client for API testing"""
    from httpx import AsyncClient
    from app.main import app
    from app.db.base import get_db

    async def override_get_db():
        yield db_session_async

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def sync_client():
    """Provide sync HTTP client (using TestClient)"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    return TestClient(app)


# === Mocking Fixtures ===

@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client"""
    mock = mocker.AsyncMock()
    mock.get = mocker.AsyncMock(return_value=None)
    mock.set = mocker.AsyncMock(return_value=True)
    mock.delete = mocker.AsyncMock(return_value=True)
    mock.expire = mocker.AsyncMock(return_value=True)
    mock.ttl = mocker.AsyncMock(return_value=-1)
    
    return mock


@pytest.fixture
def mock_celery_task(mocker):
    """Mock Celery task execution"""
    return mocker.patch("app.workers.tasks.delay")


@pytest.fixture
def mock_openai(mocker):
    """Mock OpenAI API calls"""
    mock = mocker.AsyncMock()
    mock.create_completion = mocker.AsyncMock(
        return_value={
            "choices": [{"text": "Test completion"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        }
    )
    return mock


@pytest.fixture
def mock_aws_s3(mocker):
    """Mock AWS S3 operations"""
    mock = mocker.MagicMock()
    mock.upload_file = mocker.MagicMock(return_value={"ETag": "test-etag"})
    mock.download_file = mocker.MagicMock(return_value=True)
    mock.list_objects = mocker.MagicMock(return_value={"Contents": []})
    
    return mock


# === Sample Data Fixtures ===

@pytest.fixture
def sample_agent_data():
    """Provide sample agent data"""
    return {
        "id": "agent-test-123",
        "name": "Test Agent",
        "type": "linux",
        "status": "online",
        "hostname": "test-host",
        "os_type": "Linux",
        "os_version": "5.15.0",
        "tenant_id": "tenant-test-123",
        "version": "3.0.0",
    }


@pytest.fixture
def sample_alert_data():
    """Provide sample alert data"""
    return {
        "id": "alert-test-123",
        "tenant_id": "tenant-test-123",
        "name": "High CPU Alert",
        "metric": "cpu_usage",
        "threshold": 80,
        "operator": ">",
        "severity": "high",
        "enabled": True,
    }


@pytest.fixture
def sample_host_data():
    """Provide sample host data"""
    return {
        "id": "host-test-123",
        "tenant_id": "tenant-test-123",
        "hostname": "production-server-01",
        "ip_address": "192.168.1.10",
        "os_type": "Linux",
        "os_version": "Ubuntu 22.04",
        "cpu_cores": 8,
        "memory_gb": 32,
        "status": "healthy",
    }


# === Time/Date Fixtures ===

@pytest.fixture
def frozen_time(mocker):
    """Provide frozen time for consistent testing"""
    from freezegun import freeze_time
    
    frozen = freeze_time("2024-04-16 12:00:00")
    frozen.start()
    
    yield frozen
    
    frozen.stop()


@pytest.fixture
def sample_timestamp():
    """Provide sample timestamp"""
    return datetime.now(tz=timezone.utc)


# === Markers for Test Organization ===

def pytest_configure(config):
    """Register custom pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "db: Tests requiring database")
    config.addinivalue_line("markers", "cache: Tests requiring cache")
    config.addinivalue_line("markers", "external: Tests with external API calls")
