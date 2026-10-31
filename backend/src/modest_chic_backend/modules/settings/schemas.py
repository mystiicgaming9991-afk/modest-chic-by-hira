"""Pydantic request/response schemas for store settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StoreSettingUpdate(BaseModel):
    """Request body for updating a non-secret setting."""

    key: str = Field(min_length=1, max_length=100)
    value: Any
    version: int = Field(ge=1)


class StoreSettingSecretUpdate(BaseModel):
    """Request body for writing a secret setting value."""

    key: str = Field(min_length=1, max_length=100)
    value: Any
    version: int = Field(ge=1)


class StoreSettingRead(BaseModel):
    """Response body for a visible (non-secret or masked) setting."""

    key: str
    value: Any  # "***" for secrets
    is_secret: bool
    version: int
    updated_by: UUID | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreSettingListResponse(BaseModel):
    """Wrapper for the list of visible settings."""

    items: list[StoreSettingRead]


class SecretSettingReadResponse(BaseModel):
    """Response body for reading a single decrypted secret."""

    key: str
    value: Any


# ── Key Registry ──────────────────────────────────────────────────

# Allowed setting keys with their type constraints and secrecy flag.
# Only keys in this registry can be written.
ALLOWED_SETTING_KEYS: dict[str, dict[str, Any]] = {
    "fulfillment.availability": {
        "type": "object",
        "is_secret": False,
        "description": "Whether fulfillment services are available for each method.",
    },
    "operational.quote_timeout_seconds": {
        "type": "integer",
        "is_secret": False,
        "description": "Seconds before a manual quote expires.",
    },
    "operational.order_lock_timeout_seconds": {
        "type": "integer",
        "is_secret": False,
        "description": "Seconds before a cart reservation lock expires.",
    },
    "provider.resend_api_key": {
        "type": "string",
        "is_secret": True,
        "description": "Resend API key for transactional email delivery.",
    },
    "checkout.guest_allowed": {
        "type": "boolean",
        "is_secret": False,
        "description": "Whether guest checkout is enabled.",
    },
    "checkout.cod_allowed": {
        "type": "boolean",
        "is_secret": False,
        "description": "Whether cash on delivery is offered.",
    },
    "checkout.online_payment_allowed": {
        "type": "boolean",
        "is_secret": False,
        "description": "Whether online payment is offered.",
    },
    "checkout.delivery_fee_minor": {
        "type": "integer",
        "is_secret": False,
        "description": "Approved flat delivery charge in PKR minor units.",
    },
    "pickup.available": {
        "type": "boolean",
        "is_secret": False,
        "description": "Whether in-store pickup is available.",
    },
    "returns.window_days": {
        "type": "integer",
        "is_secret": False,
        "description": "Default return window in days.",
    },
}


def validate_setting_key(key: str) -> dict[str, Any]:
    """Return the key's registry entry or raise ValueError."""
    if key not in ALLOWED_SETTING_KEYS:
        raise ValueError(f"unknown setting key: {key}")
    return ALLOWED_SETTING_KEYS[key]


def validate_setting_value(key: str, value: Any) -> None:
    """Validate a setting's JSON type and keep unapproved fulfillment disabled."""
    entry = validate_setting_key(key)
    value_type = entry["type"]
    valid = (
        type(value) is bool
        if value_type == "boolean"
        else type(value) is int
        if value_type == "integer"
        else isinstance(value, dict)
        if value_type == "object"
        else isinstance(value, str) and bool(value.strip())
    )
    if not valid:
        raise ValueError(f"setting '{key}' must be a {value_type}")

    if value_type == "integer" and (value < 0 or (key == "returns.window_days" and value == 0)):
        raise ValueError(f"setting '{key}' must be a valid non-negative whole number")
    if key == "checkout.online_payment_allowed" and value is True:
        raise ValueError("online payment is unavailable until provider setup and approval")
    if key == "pickup.available" and value is True:
        raise ValueError(
            "pickup is unavailable until an approved location and hours are configured"
        )
    if key == "fulfillment.availability":
        for flag in ("delivery", "pickup"):
            if flag in value and type(value[flag]) is not bool:
                raise ValueError(f"fulfillment.availability.{flag} must be a boolean")
        for cities_key in ("delivery_cities", "pickup_cities"):
            cities = value.get(cities_key)
            if cities is not None and (
                not isinstance(cities, list)
                or any(not isinstance(city, str) or not city.strip() for city in cities)
            ):
                raise ValueError(f"fulfillment.availability.{cities_key} must be a list of cities")
        if value.get("pickup") is True:
            raise ValueError(
                "pickup is unavailable until an approved location and hours are configured"
            )
