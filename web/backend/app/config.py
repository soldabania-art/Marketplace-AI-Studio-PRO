from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Marketplace AI Studio API"
    environment: str = "development"
    database_url: str = "sqlite:///./marketplace_cloud.db"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    session_days: int = 7
    login_attempt_window_minutes: int = 15
    login_attempt_max_failures: int = 5
    email_verification_hours: int = 24
    password_reset_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    admin_emails: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MARKETPLACE_", extra="ignore")

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
