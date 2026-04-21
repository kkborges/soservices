"""
Database engine, session factory and base model.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import Column, String, DateTime, func, text
from app.core.config import settings
import uuid


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    __allow_unmapped__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    from app.services.seed_service import ensure_initial_data
    from app.services.mtls_service import issue_api_server_certificate

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_schema_migrations(conn)
    async with AsyncSessionLocal() as session:
        await ensure_initial_data(session)

    # Ensure the mTLS CA and API server certificate exist on disk for the mTLS edge proxy.
    # This is safe and idempotent and avoids shipping certificate artifacts inside git.
    try:
        issue_api_server_certificate()
    except Exception:
        # Avoid blocking startup: the platform can still run without mTLS edge on first boot,
        # but installers will require this to be healthy.
        pass


async def ensure_schema_migrations(conn):
    """Small idempotent upgrade path for installations without Alembic yet."""
    statements = [
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS application VARCHAR(255)",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS url VARCHAR(2000)",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS status_code INTEGER",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS server_time_ms DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS network_time_ms DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS client_time_ms DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS span_id VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS service VARCHAR(255)",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS satisfied BOOLEAN DEFAULT TRUE",
        "ALTER TABLE IF EXISTS rum_events ADD COLUMN IF NOT EXISTS metadata JSON DEFAULT '{}'::json",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS application VARCHAR(255)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS browser VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS os VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS country VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS region VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS live BOOLEAN DEFAULT TRUE",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS satisfaction_index DOUBLE PRECISION DEFAULT 100",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS requests_total INTEGER DEFAULT 0",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS actions_total INTEGER DEFAULT 0",
        "ALTER TABLE IF EXISTS rum_sessions ADD COLUMN IF NOT EXISTS errors_total INTEGER DEFAULT 0",
        "ALTER TABLE IF EXISTS tickets ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 3",
        "ALTER TABLE IF EXISTS tickets ALTER COLUMN created_by DROP NOT NULL",
        """
        DO $$
        BEGIN
            IF to_regclass('public.rum_events') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_events' AND column_name='app_name'
            ) THEN
                ALTER TABLE rum_events ALTER COLUMN app_name DROP NOT NULL;
                UPDATE rum_events SET application = COALESCE(application, app_name) WHERE application IS NULL AND app_name IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_events') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_events' AND column_name='page_url'
            ) THEN
                UPDATE rum_events SET url = COALESCE(url, page_url) WHERE url IS NULL AND page_url IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_events') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_events' AND column_name='resource_url'
            ) THEN
                UPDATE rum_events SET url = COALESCE(url, resource_url) WHERE url IS NULL AND resource_url IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_events') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_events' AND column_name='response_code'
            ) THEN
                UPDATE rum_events SET status_code = COALESCE(status_code, response_code) WHERE status_code IS NULL AND response_code IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_events') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_events' AND column_name='service_name'
            ) THEN
                UPDATE rum_events SET service = COALESCE(service, service_name) WHERE service IS NULL AND service_name IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_sessions') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_sessions' AND column_name='app_name'
            ) THEN
                ALTER TABLE rum_sessions ALTER COLUMN app_name DROP NOT NULL;
                UPDATE rum_sessions SET application = COALESCE(application, app_name) WHERE application IS NULL AND app_name IS NOT NULL;
            END IF;
            IF to_regclass('public.rum_sessions') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_sessions' AND column_name='ended_at'
            ) THEN
                UPDATE rum_sessions SET last_seen = COALESCE(last_seen, ended_at, started_at) WHERE last_seen IS NULL;
                UPDATE rum_sessions SET live = COALESCE(live, ended_at IS NULL, TRUE) WHERE live IS NULL;
            END IF;
            IF to_regclass('public.rum_sessions') IS NOT NULL AND EXISTS (
                SELECT 1 FROM information_schema.columns WHERE table_name='rum_sessions' AND column_name='total_requests'
            ) THEN
                UPDATE rum_sessions SET requests_total = COALESCE(requests_total, total_requests, 0) WHERE requests_total IS NULL;
                UPDATE rum_sessions SET actions_total = COALESCE(actions_total, total_actions, 0) WHERE actions_total IS NULL;
                UPDATE rum_sessions SET errors_total = COALESCE(errors_total, total_errors, 0) WHERE errors_total IS NULL;
            END IF;
        END $$;
        """,
    ]
    for statement in statements:
        await conn.execute(text(statement))
