"""Store settings business logic — encryption, validation, and audit."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.settings.crypto import (
    decrypt_setting_value,
    encrypt_setting_value,
)
from modest_chic_backend.modules.settings.repository import SettingsRepository
from modest_chic_backend.modules.settings.schemas import (
    StoreSettingRead,
    validate_setting_key,
    validate_setting_value,
)

_SECRET_PLACEHOLDER = "***"


class SettingsService:
    """Application service for reading and writing versioned store settings."""

    def __init__(self, session: AsyncSession, encryption_key: bytes) -> None:
        self._session = session
        self._repo = SettingsRepository(session)
        self._audit = AuditRepository(session)
        self._encryption_key = encryption_key

    async def get_all_visible(self) -> list[StoreSettingRead]:
        """Return all settings, masking secret values with '***'."""
        rows = await self._repo.get_all()
        return [
            StoreSettingRead(
                key=row.key,
                value=_SECRET_PLACEHOLDER if row.is_secret else row.value,
                is_secret=row.is_secret,
                version=row.version,
                updated_by=row.updated_by,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def update_setting(
        self,
        key: str,
        value: Any,
        version: int,
        actor_id: uuid.UUID,
    ) -> StoreSettingRead:
        """Update a non-secret setting with version-checked concurrency.

        Args:
            key: The stable setting key (must be in the allowed key registry).
            value: The new JSON-serializable value.
            version: The version the caller believes is current.
            actor_id: The staff user making the change.

        Returns:
            The updated setting (with the new version).

        Raises:
            ValueError: If the key is unknown, is a secret, or version conflicts.
        """
        entry = validate_setting_key(key)
        if entry["is_secret"]:
            raise ValueError(f"setting '{key}' is secret; use update_secret instead")
        validate_setting_value(key, value)

        row = await self._repo.upsert_with_version_check(
            key=key, value=value, version=version, updated_by=actor_id
        )
        await self._audit.record(
            action="settings.updated",
            entity_type="store_setting",
            actor_id=actor_id,
            entity_id=row.id,
            metadata={"key": key, "version": row.version},
        )
        await self._session.refresh(row)
        return StoreSettingRead(
            key=row.key,
            value=row.value,
            is_secret=row.is_secret,
            version=row.version,
            updated_by=row.updated_by,
            updated_at=row.updated_at,
        )

    async def update_secret(
        self,
        key: str,
        value: Any,
        version: int,
        actor_id: uuid.UUID,
    ) -> StoreSettingRead:
        """Encrypt and write a secret setting value.

        The plaintext value is encrypted before storage. The response
        still shows '***' as the value.

        Args:
            key: The stable setting key.
            value: The plaintext secret value to encrypt and store.
            version: The version the caller believes is current.
            actor_id: The staff user making the change.

        Returns:
            The updated setting with '***' as the displayed value.
        """
        entry = validate_setting_key(key)
        if not entry["is_secret"]:
            raise ValueError(f"setting '{key}' is not a secret; use update_setting")
        validate_setting_value(key, value)

        encrypted = encrypt_setting_value(self._encryption_key, value)
        row = await self._repo.upsert_with_version_check(
            key=key, value=encrypted, version=version, updated_by=actor_id
        )
        # Ensure the is_secret flag is set
        if not row.is_secret:
            row.is_secret = True

        await self._audit.record(
            action="settings.secret_updated",
            entity_type="store_setting",
            actor_id=actor_id,
            entity_id=row.id,
            metadata={"key": key, "version": row.version},
        )
        await self._session.refresh(row)
        return StoreSettingRead(
            key=row.key,
            value=_SECRET_PLACEHOLDER,
            is_secret=True,
            version=row.version,
            updated_by=row.updated_by,
            updated_at=row.updated_at,
        )

    async def get_decrypted_secret(self, key: str, actor_id: uuid.UUID) -> dict[str, Any]:
        """Read and decrypt a single secret setting value.

        Args:
            key: The setting key (must be a secret).
            actor_id: The staff user making the request (for audit).

        Returns:
            A dict with 'key' and the decrypted 'value'.

        Raises:
            ValueError: If the key is unknown or not a secret.
            LookupError: If no setting exists with this key.
        """
        entry = validate_setting_key(key)
        if not entry["is_secret"]:
            raise ValueError(f"setting '{key}' is not a secret")

        row = await self._repo.get_by_key(key)
        if row is None:
            raise LookupError(f"no setting found for key: {key}")

        decrypted = decrypt_setting_value(self._encryption_key, row.value)
        await self._audit.record(
            action="settings.secret_read",
            entity_type="store_setting",
            actor_id=actor_id,
            entity_id=row.id,
            metadata={"key": key},
        )
        return {"key": key, "value": decrypted}
