from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Marketplace AI Studio API"
    environment: str = "development"
    database_url: str = "sqlite:///./marketplace_cloud.db"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MARKETPLACE_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
