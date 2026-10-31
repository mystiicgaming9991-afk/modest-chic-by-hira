"""Unit tests for settings service business logic."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from modest_chic_backend.modules.settings.models import StoreSetting
from modest_chic_backend.modules.settings.schemas import (
    ALLOWED_SETTING_KEYS,
    validate_setting_key,
    validate_setting_value,
)
from modest_chic_backend.modules.settings.service import _SECRET_PLACEHOLDER, SettingsService


def _now() -> datetime:
    return datetime.now(UTC)


# ── Key Registry ──────────────────────────────────────────────────


def test_validate_known_key_returns_entry() -> None:
    entry = validate_setting_key("checkout.guest_allowed")
    assert entry == ALLOWED_SETTING_KEYS["checkout.guest_allowed"]


def test_validate_unknown_key_raises() -> None:
    with pytest.raises(ValueError, match="unknown setting key"):
        validate_setting_key("nonexistent.key")


def test_secret_keys_marked_as_secret() -> None:
    entry = validate_setting_key("provider.resend_api_key")
    assert entry["is_secret"] is True


def test_non_secret_keys_not_marked_secret() -> None:
    entry = validate_setting_key("checkout.cod_allowed")
    assert entry["is_secret"] is False


# ── update_setting ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("checkout.guest_allowed", 1),
        ("checkout.delivery_fee_minor", True),
        ("fulfillment.availability", []),
        ("provider.resend_api_key", "  "),
    ],
)
def test_setting_value_rejects_wrong_json_types(key: str, value: object) -> None:
    with pytest.raises(ValueError, match="must be"):
        validate_setting_value(key, value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("checkout.online_payment_allowed", True),
        ("pickup.available", True),
        ("fulfillment.availability", {"pickup": True, "pickup_cities": ["Karachi"]}),
    ],
)
def test_unapproved_payment_and_pickup_settings_remain_disabled(key: str, value: object) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        validate_setting_value(key, value)


async def test_update_setting_calls_repository_and_audit() -> None:
    """update_setting invokes the repository with version check and records audit."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    row = StoreSetting(
        key="checkout.guest_allowed",
        value=True,
        is_secret=False,
        version=2,
        updated_by=None,
        updated_at=_now(),
    )
    row.id = uuid.uuid4()

    with patch.object(
        service._repo, "upsert_with_version_check", new_callable=AsyncMock
    ) as mock_upsert:
        mock_upsert.return_value = row
        with patch.object(service._audit, "record", new_callable=AsyncMock) as mock_audit:
            result = await service.update_setting(
                key="checkout.guest_allowed",
                value=True,
                version=1,
                actor_id=uuid.uuid4(),
            )

    mock_upsert.assert_awaited_once()
    mock_audit.assert_awaited_once()
    assert result.key == "checkout.guest_allowed"
    assert result.value is True
    assert result.version == 2


async def test_update_setting_on_secret_key_raises() -> None:
    """Calling update_setting on a secret key raises ValueError."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    with pytest.raises(ValueError, match="secret"):
        await service.update_setting(
            key="provider.resend_api_key",
            value="re_key",
            version=1,
            actor_id=uuid.uuid4(),
        )


async def test_update_setting_unknown_key_raises() -> None:
    """Calling update_setting with an unknown key raises ValueError."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    with pytest.raises(ValueError, match="unknown setting key"):
        await service.update_setting(
            key="made.up.key",
            value="anything",
            version=1,
            actor_id=uuid.uuid4(),
        )


# ── update_secret ─────────────────────────────────────────────────


async def test_update_secret_encrypts_before_storage() -> None:
    """update_secret encrypts the value before storage and returns '***'."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"s" * 32)

    row = StoreSetting(
        key="provider.resend_api_key",
        value={"v": 1, "ciphertext": "enc", "nonce": "non"},
        is_secret=True,
        version=2,
        updated_at=_now(),
    )
    row.id = uuid.uuid4()

    with patch.object(
        service._repo, "upsert_with_version_check", new_callable=AsyncMock
    ) as mock_upsert:
        mock_upsert.return_value = row
        with patch.object(service._audit, "record", new_callable=AsyncMock) as mock_audit:
            result = await service.update_secret(
                key="provider.resend_api_key",
                value="re_actual_secret",
                version=1,
                actor_id=uuid.uuid4(),
            )

    stored_value = mock_upsert.call_args.kwargs["value"]
    assert isinstance(stored_value, dict)
    assert stored_value["v"] == 1
    assert "ciphertext" in stored_value
    assert "nonce" in stored_value
    assert stored_value != "re_actual_secret"

    mock_audit.assert_awaited_once()
    assert result.value == "***"


async def test_update_secret_on_non_secret_key_raises() -> None:
    """Calling update_secret on a non-secret key raises ValueError."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    with pytest.raises(ValueError, match="not a secret"):
        await service.update_secret(
            key="checkout.guest_allowed",
            value="anything",
            version=1,
            actor_id=uuid.uuid4(),
        )


# ── get_decrypted_secret ──────────────────────────────────────────


async def test_get_decrypted_secret_round_trip() -> None:
    """get_decrypted_secret decrypts the stored value."""
    from modest_chic_backend.modules.settings.crypto import encrypt_setting_value

    key_bytes = b"s" * 32
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=key_bytes)

    plaintext = "re_live_secret_key"
    encrypted = encrypt_setting_value(key_bytes, plaintext)

    row = StoreSetting(
        key="provider.resend_api_key",
        value=encrypted,
        is_secret=True,
        version=1,
        updated_at=_now(),
    )
    row.id = uuid.uuid4()

    with patch.object(service._repo, "get_by_key", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = row
        with patch.object(service._audit, "record", new_callable=AsyncMock) as mock_audit:
            result = await service.get_decrypted_secret(
                key="provider.resend_api_key",
                actor_id=uuid.uuid4(),
            )

    assert result == {"key": "provider.resend_api_key", "value": plaintext}
    mock_audit.assert_awaited_once()


async def test_get_decrypted_on_non_secret_key_raises() -> None:
    """get_decrypted_secret on a non-secret key raises ValueError."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    with pytest.raises(ValueError, match="not a secret"):
        await service.get_decrypted_secret(
            key="checkout.guest_allowed",
            actor_id=uuid.uuid4(),
        )


async def test_get_decrypted_missing_key_raises_lookup_error() -> None:
    """When no setting exists for a secret key, raises LookupError."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    with patch.object(service._repo, "get_by_key", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        with pytest.raises(LookupError, match="no setting found"):
            await service.get_decrypted_secret(
                key="provider.resend_api_key",
                actor_id=uuid.uuid4(),
            )


# ── get_all_visible ───────────────────────────────────────────────


async def test_get_all_visible_masks_secret_values() -> None:
    """Secret settings show '***' while non-secrets show their actual value."""
    mock_session = AsyncMock()
    service = SettingsService(mock_session, encryption_key=b"k" * 32)

    row1 = StoreSetting(
        key="checkout.guest_allowed", value=True, is_secret=False, version=1, updated_at=_now()
    )
    row1.id = uuid.uuid4()
    row2 = StoreSetting(
        key="provider.resend_api_key",
        value={"v": 1, "ciphertext": "x", "nonce": "y"},
        is_secret=True,
        version=1,
        updated_at=_now(),
    )
    row2.id = uuid.uuid4()

    with patch.object(service._repo, "get_all", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [row1, row2]
        items = await service.get_all_visible()

    assert len(items) == 2
    non_secret = next(item for item in items if item.key == "checkout.guest_allowed")
    assert non_secret.value is True
    secret = next(item for item in items if item.key == "provider.resend_api_key")
    assert secret.value == _SECRET_PLACEHOLDER
