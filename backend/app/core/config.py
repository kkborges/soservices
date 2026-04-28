"""
LAS Platform — Core Configuration
"""
import secrets
from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────────────
    APP_NAME: str = "LAS Plataforma de Monitoramento e Observabilidade"
    APP_VERSION: str = "4.1.0"
    DEBUG: bool = False
    API_DOCS_ENABLED: bool = True
    SECRET_KEY: str = secrets.token_urlsafe(64)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Server ─────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    PLATFORM_URL: str = "https://api.soservices.com.br"
    PUBLIC_WEB_URL: str = "https://las.soservices.com.br"
    MTLS_ENABLED: bool = True
    MTLS_REQUIRED: bool = True
    MTLS_PLATFORM_URL: str = "https://api.soservices.com.br:8443"
    MTLS_STORAGE_DIR: str = "/app/runtime/mtls"
    MTLS_CA_COMMON_NAME: str = "LAS Platform Internal CA"

    # ── Database ───────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "las"
    POSTGRES_USER: str = "las"
    POSTGRES_PASSWORD: str = "las_password_change_me"

    @property
    def DATABASE_URL(self) -> str:
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis / Celery ─────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SENTINELS: Optional[str] = None
    REDIS_MASTER_NAME: str = "lasmaster"

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            password = quote_plus(self.REDIS_PASSWORD)
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # ── AI Providers ───────────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_CODEX_MODEL: str = "gpt-5.3-codex"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    AI_PROVIDER: str = "openai"   # openai | anthropic | gemini

    # ── Email (SMTP) ───────────────────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "las@yourdomain.com"
    SMTP_TLS: bool = True

    # ── Notification Channels ──────────────────────────────────────
    SLACK_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TEAMS_WEBHOOK_URL: Optional[str] = None
    WHATSAPP_TOKEN: Optional[str] = None
    PAGERDUTY_KEY: Optional[str] = None
    OPSGENIE_KEY: Optional[str] = None
    DISCORD_WEBHOOK: Optional[str] = None

    # ── Cloud Integrations ─────────────────────────────────────────
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"

    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    AZURE_SUBSCRIPTION_ID: Optional[str] = None

    GCP_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ── Kubernetes ─────────────────────────────────────────────────
    KUBECONFIG_PATH: Optional[str] = None
    K8S_IN_CLUSTER: bool = False

    # ── VMware ─────────────────────────────────────────────────────
    VMWARE_HOST: Optional[str] = None
    VMWARE_USER: Optional[str] = None
    VMWARE_PASSWORD: Optional[str] = None
    VMWARE_PORT: int = 443

    # ── OTel Collector ─────────────────────────────────────────────
    OTEL_COLLECTOR_GRPC: str = "localhost:4317"
    OTEL_COLLECTOR_HTTP: str = "localhost:4318"

    # ── Agent / Gateway tokens ─────────────────────────────────────
    AGENT_TOKEN_PREFIX: str = "lsa"
    GATEWAY_TOKEN_PREFIX: str = "lsg"

    # Initial bootstrap
    INITIAL_TENANT_NAME: str = "SOServices Platform Admin"
    INITIAL_TENANT_SLUG: str = "platform-admin"
    INITIAL_ADMIN_NAME: str = "Administrador SOServices"
    INITIAL_ADMIN_EMAIL: str = "admin@soservices.com.br"
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "admin"
    DEMO_TENANT_NAME: str = "Demo"
    DEMO_TENANT_SLUG: str = "demo"
    DEMO_ADMIN_NAME: str = "Demo LAS"
    DEMO_ADMIN_EMAIL: str = "demo_las@soservices.com.br"
    DEMO_ADMIN_USERNAME: str = "demo_las@soservices.com.br"
    DEMO_ADMIN_PASSWORD: str = "admin"
    TRIAL_DAYS: int = 15

    # ── Synthetic Tests ────────────────────────────────────────────
    SYNTHETIC_WORKERS: int = 10
    SYNTHETIC_TIMEOUT_S: int = 30
    SYNTHETIC_INTERVAL_MIN: int = 1

    # ── AI Baseline / Anomaly ──────────────────────────────────────
    BASELINE_WINDOW_HOURS: int = 168    # 1 week
    BASELINE_ANOMALY_STD: float = 3.0   # 3-sigma rule
    AI_ANALYSIS_INTERVAL_MIN: int = 5
    AI_SECURITY_ANALYSIS_INTERVAL_MIN: int = 2

    # ── CORS ───────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance"""
    return settings
