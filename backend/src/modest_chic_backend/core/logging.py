"""Structured logging processors that remove credentials and personal data."""

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

SENSITIVE_FIELD_PARTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "email",
    "phone",
    "address",
    "reset_link",
    "invitation_link",
)
SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)(password|token|secret|authorization|cookie|email|phone|address|reset_link)"
    r"([=:]\s*)([^\s,;]+)"
)


def redact_sensitive_fields(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> dict[str, Any]:
    """Redact sensitive keys recursively before a structured event is emitted."""
    del logger, method_name
    return _redact_mapping(event_dict)


def _redact_mapping(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively redacted copy of a structured event mapping."""
    redacted: dict[str, Any] = {}
    for key, value in event.items():
        normalized_key = key.lower().replace("-", "_")
        if any(part in normalized_key for part in SENSITIVE_FIELD_PARTS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            redacted[key] = _redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [_redact_value(item) for item in value]
        else:
            redacted[key] = _redact_value(value)
    return redacted


def _redact_value(value: Any) -> Any:
    """Redact credentials embedded in text while preserving safe values."""
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, str):
        return SENSITIVE_TEXT_PATTERN.sub(r"\1\2[REDACTED]", value)
    return value


def configure_logging() -> None:
    """Configure JSON structured logs with redaction before serialization."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )
