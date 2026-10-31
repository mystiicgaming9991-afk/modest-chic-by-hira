import pytest
from pydantic import ValidationError

from modest_chic_backend.core.settings import Settings


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+asyncpg://modest:modest@localhost/modest",
        "redis_url": "redis://localhost:6379/0",
        "jwt_signing_key": "j" * 32,
        "csrf_signing_key": "c" * 32,
        "totp_encryption_key": "t" * 32,
        "outbox_encryption_key": "o" * 32,
        "trusted_origins": ["http://localhost:3000"],
        "admin_base_url": "http://localhost:3000/admin",
        "email_provider": "console",
        "email_from": "admin@localhost",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_accept_explicit_nonproduction_secrets() -> None:
    settings = build_settings()

    assert settings.access_token_ttl_seconds == 900
    assert settings.refresh_token_ttl_seconds == 604800
    assert settings.trusted_origins == ["http://localhost:3000"]


def test_production_settings_reject_http_origins() -> None:
    with pytest.raises(ValidationError):
        build_settings(app_env="production", trusted_origins=["http://localhost:3000"])


def test_settings_reject_short_secrets() -> None:
    with pytest.raises(ValidationError):
        build_settings(jwt_signing_key="short")


def test_settings_reject_nonpositive_token_lifetime() -> None:
    with pytest.raises(ValidationError):
        build_settings(access_token_ttl_seconds=0)
