from functools import lru_cache
import secrets
from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "TROVENDI API"
    environment: str = "development"
    database_url: str = "sqlite:///./marketplace_cloud.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    session_days: int = 7
    session_last_seen_write_seconds: int = 300
    login_attempt_window_minutes: int = 15
    login_attempt_max_failures: int = 5
    login_ip_max_failures: int = 25
    account_action_window_minutes: int = 15
    account_action_subject_limit: int = 5
    account_action_ip_limit: int = 25
    max_request_body_bytes: int = 20 * 1024 * 1024
    email_verification_hours: int = 24
    password_reset_minutes: int = 30
    mfa_encryption_key: str = ""
    mfa_challenge_minutes: int = 5
    mfa_attempt_limit: int = 8
    mfa_setup_minutes: int = 10
    step_up_minutes: int = 10
    frontend_url: str = "http://localhost:3000"
    admin_emails: str = ""
    billing_provider: str = "not_configured"
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""
    marketplace_token_key: str = ""
    marketplace_secret_provider: str = "fernet"
    marketplace_default_min_interval_seconds: float = 2.0
    marketplace_limiter_backend: str = "memory"
    redis_url: str = ""
    redis_key_prefix: str = "mai"
    fbo_poll_seconds: int = 60
    fbo_worker_concurrency: int = 12
    fbo_account_min_interval_seconds: int = 10
    fbo_cycle_jitter_seconds: int = 5
    run_fbo_monitor_in_api: bool = False
    job_worker_concurrency: int = 8
    job_idle_poll_seconds: float = 1.0
    job_lease_seconds: int = 300
    job_retry_base_seconds: int = 10
    job_retry_max_seconds: int = 900
    job_priority_aging_seconds: int = 300
    sync_scheduler_seconds: int = 60
    sync_analytics_interval_seconds: int = 1800
    sync_finance_interval_seconds: int = 86400
    sync_advertising_interval_seconds: int = 86400
    sync_dead_retry_interval_seconds: int = 3600
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-terra"
    openai_timeout_seconds: float = 60.0
    openai_input_microusd_per_million_tokens: int = 0
    openai_output_microusd_per_million_tokens: int = 0
    openai_image_model: str = "gpt-image-1-mini"
    openai_image_quality: str = "low"
    openai_image_size: str = "1024x1024"
    openai_image_timeout_seconds: float = 120.0
    openai_image_estimated_cost_microusd: int = 5000
    document_scan_webhook_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MARKETPLACE_", extra="ignore")

    @model_validator(mode="after")
    def secure_runtime_secrets(self):
        if not self.jwt_secret:
            if self.is_production:
                raise ValueError("MARKETPLACE_JWT_SECRET is required in production")
            self.jwt_secret = secrets.token_urlsafe(48)
        if not self.mfa_encryption_key and not self.is_production:
            self.mfa_encryption_key = Fernet.generate_key().decode()
        if self.is_production and len(self.jwt_secret) < 32:
            raise ValueError("MARKETPLACE_JWT_SECRET must contain at least 32 characters in production")
        if self.is_production:
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
                raise ValueError("MARKETPLACE_DATABASE_URL must use PostgreSQL in production")
            tls_markers = ("sslmode=require", "sslmode=verify-full", "ssl=true")
            if not any(marker in self.database_url.lower() for marker in tls_markers):
                raise ValueError("MARKETPLACE_DATABASE_URL must require TLS in production")
            if not self.marketplace_token_key:
                raise ValueError("MARKETPLACE_MARKETPLACE_TOKEN_KEY is required in production")
            if not self.mfa_encryption_key:
                raise ValueError("MARKETPLACE_MFA_ENCRYPTION_KEY is required in production")
            if self.marketplace_secret_provider.strip().lower() != "fernet":
                raise ValueError("Unsupported marketplace secret provider")
            try:
                Fernet(self.marketplace_token_key.encode())
            except Exception as exc:
                raise ValueError("MARKETPLACE_MARKETPLACE_TOKEN_KEY must be a valid Fernet key") from exc
            try:
                Fernet(self.mfa_encryption_key.encode())
            except Exception as exc:
                raise ValueError("MARKETPLACE_MFA_ENCRYPTION_KEY must be a valid Fernet key") from exc
            if self.jwt_algorithm != "HS256":
                raise ValueError("MARKETPLACE_JWT_ALGORITHM must be HS256 in production")
            if not self.frontend_url.lower().startswith("https://"):
                raise ValueError("MARKETPLACE_FRONTEND_URL must use HTTPS in production")
        return self

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def billing_is_configured(self) -> bool:
        return self.billing_provider.strip().lower() not in {"", "none", "not_configured"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
