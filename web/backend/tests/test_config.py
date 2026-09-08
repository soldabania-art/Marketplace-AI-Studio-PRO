import pytest
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

    settings = Settings(environment="production", jwt_secret="x" * 48, _env_file=None)
    assert settings.jwt_secret == "x" * 48
