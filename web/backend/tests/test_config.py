import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings


def test_development_gets_ephemeral_strong_jwt_secret():
    settings = Settings(environment="development", jwt_secret="", _env_file=None)
    assert len(settings.jwt_secret) >= 32


def test_production_requires_explicit_strong_jwt_secret():
    with pytest.raises(ValidationError, match="MARKETPLACE_JWT_SECRET is required"):
        Settings(environment="production", jwt_secret="", _env_file=None)

    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(environment="production", jwt_secret="too-short", _env_file=None)

    settings = Settings(
        environment="production",
        jwt_secret="x" * 48,
        database_url="postgresql+psycopg://app:secret@db.internal/trovendi?sslmode=require",
        marketplace_token_key=Fernet.generate_key().decode(),
        frontend_url="https://trovendi.ru",
        _env_file=None,
    )
    assert settings.jwt_secret == "x" * 48


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"database_url": "sqlite:///production.db"}, "must use PostgreSQL"),
        ({"database_url": "postgresql+psycopg://app:secret@db.internal/trovendi"}, "must require TLS"),
        ({"marketplace_token_key": ""}, "TOKEN_KEY is required"),
        ({"marketplace_token_key": "not-a-fernet-key"}, "must be a valid Fernet key"),
        ({"jwt_algorithm": "none"}, "must be HS256"),
        ({"frontend_url": "http://trovendi.ru"}, "must use HTTPS"),
    ],
)
def test_production_rejects_insecure_runtime_configuration(override, message):
    values = {
        "environment": "production",
        "jwt_secret": "x" * 48,
        "database_url": "postgresql+psycopg://app:secret@db.internal/trovendi?sslmode=require",
        "marketplace_token_key": Fernet.generate_key().decode(),
        "frontend_url": "https://trovendi.ru",
        "_env_file": None,
    }
    values.update(override)
    with pytest.raises(ValidationError, match=message):
        Settings(**values)
