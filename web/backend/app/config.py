from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Marketplace AI Studio API"
    environment: str = "development"
    database_url: str = "sqlite:///./marketplace_cloud.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    session_days: int = 7
    session_last_seen_write_seconds: int = 300
    login_attempt_window_minutes: int = 15
    login_attempt_max_failures: int = 5
    email_verification_hours: int = 24
    password_reset_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    admin_emails: str = ""
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
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MARKETPLACE_", extra="ignore")

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
