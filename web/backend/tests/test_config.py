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
        mfa_encryption_key=Fernet.generate_key().decode(),
        frontend_url="https://trovendi.ru",
        marketplace_limiter_backend="redis",
        redis_url="rediss://redis.internal:6379/0",
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
        ({"mfa_encryption_key": ""}, "MFA_ENCRYPTION_KEY is required"),
        ({"mfa_encryption_key": "not-a-fernet-key"}, "MFA_ENCRYPTION_KEY must be a valid Fernet key"),
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
        "mfa_encryption_key": Fernet.generate_key().decode(),
        "frontend_url": "https://trovendi.ru",
        "marketplace_limiter_backend": "redis",
        "redis_url": "rediss://redis.internal:6379/0",
        "_env_file": None,
    }
    values.update(override)
    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_resend_requires_complete_shared_encryption_configuration():
    key = Fernet.generate_key().decode()
    settings = Settings(
        environment="development",
        email_provider="resend",
        resend_api_key="test-key",
        email_from="TROVENDI <mail@example.com>",
        email_secret_key=key,
        frontend_url="https://app.example.com",
        _env_file=None,
    )
    assert settings.email_is_configured
    assert settings.email_secret_key == key

    for field, message in (
        ("resend_api_key", "RESEND_API_KEY"),
        ("email_from", "EMAIL_FROM"),
        ("email_secret_key", "EMAIL_SECRET_KEY"),
    ):
        values = {
            "environment": "development",
            "email_provider": "resend",
            "resend_api_key": "test-key",
            "email_from": "TROVENDI <mail@example.com>",
            "email_secret_key": key,
            "frontend_url": "https://app.example.com",
            "_env_file": None,
        }
        values[field] = ""
        with pytest.raises(ValidationError, match=message):
            Settings(**values)


@pytest.mark.parametrize("frontend_url", [
    "https://user:password@app.example.com",
    "https://app.example.com/path",
    "https://app.example.com?next=evil",
    "https://app.example.com/#fragment",
])
def test_frontend_url_is_an_origin_not_an_email_link_override(frontend_url):
    with pytest.raises(ValidationError, match="trusted origin"):
        Settings(environment="development", frontend_url=frontend_url, _env_file=None)
