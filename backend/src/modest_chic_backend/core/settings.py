"""Validated runtime configuration for the API and worker."""

from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load configuration and reject unsafe production defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str
    redis_url: str
    jwt_signing_key: SecretStr
    csrf_signing_key: SecretStr
    totp_encryption_key: SecretStr
    outbox_encryption_key: SecretStr
    access_token_ttl_seconds: int = Field(default=900, gt=0, le=900)
    refresh_token_ttl_seconds: int = Field(default=604800, gt=0, le=604800)
    trusted_origins: list[str]
    admin_base_url: AnyHttpUrl
    email_provider: Literal["console", "resend"] = "console"
    resend_api_key: SecretStr | None = None
    email_from: str

    @field_validator(
        "jwt_signing_key",
        "csrf_signing_key",
        "totp_encryption_key",
        "outbox_encryption_key",
    )
    @classmethod
    def validate_secret_length(cls, value: SecretStr) -> SecretStr:
        """Require sufficient key material for configured cryptographic operations."""
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("secret must contain at least 32 UTF-8 bytes")
        return value

    @field_validator("totp_encryption_key", "outbox_encryption_key")
    @classmethod
    def validate_aes_key_length(cls, value: SecretStr) -> SecretStr:
        """Require exactly 32 bytes for AES-256 encryption keys."""
        if len(value.get_secret_value().encode("utf-8")) != 32:
            raise ValueError("AES-256 encryption keys must contain exactly 32 UTF-8 bytes")
        return value

    @field_validator("trusted_origins", mode="before")
    @classmethod
    def normalize_trusted_origins(cls, values: list[str]) -> list[str]:
        """Canonicalize origin URLs without paths or trailing slashes."""
        url_adapter = TypeAdapter(AnyHttpUrl)
        origins: list[str] = []
        for value in values:
            url = url_adapter.validate_python(value)
            if url.path not in ("", "/") or url.query or url.fragment:
                raise ValueError("trusted origins must contain only scheme, host, and port")
            origins.append(str(url).rstrip("/"))
        return origins

    @model_validator(mode="after")
    def validate_production_origins_and_mail(self) -> "Settings":
        """Prevent insecure browser origins and missing production email credentials."""
        if self.app_env == "production":
            if any(not origin.startswith("https://") for origin in self.trusted_origins):
                raise ValueError("production trusted origins must use HTTPS")
            if self.email_provider != "resend" or self.resend_api_key is None:
                raise ValueError("production requires EMAIL_PROVIDER=resend and RESEND_API_KEY")
        return self
