"""Store settings database access with optimistic concurrency control."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.settings.models import StoreSetting


class SettingsRepository:
    """Read and write store settings with version-checked upserts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, key: str) -> StoreSetting | None:
        """Return the current setting row for the given key, or None."""
        result = await self._session.execute(select(StoreSetting).where(StoreSetting.key == key))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[StoreSetting]:
        """Return all setting rows; masking of secret values is the caller's responsibility."""
        result = await self._session.execute(select(StoreSetting))
        return list(result.scalars().all())

    async def upsert_with_version_check(
        self,
        key: str,
        value: Any,
        version: int,
        updated_by: uuid.UUID | None,
    ) -> StoreSetting:
        """Insert or update a setting, requiring the current version to match.

        On a new key (no existing row), version must be 1 (the default).
        On an existing key, the requested version must equal the stored version.
        On success the stored version is incremented.

        Args:
            key: The stable setting key.
            value: The JSON-serializable new value.
            version: The version the caller believes is current.
            updated_by: The staff user making the change, or None.

        Returns:
            The updated StoreSetting row.

        Raises:
            ValueError: If the version check fails.
        """
        existing = await self.get_by_key(key)
        if existing is None:
            if version != 1:
                raise ValueError(
                    f"version conflict: new key '{key}' must start at version 1, got {version}"
                )
            setting = StoreSetting(
                key=key,
                value=value,
                is_secret=False,
                version=2,  # first write increments to 2
                updated_by=updated_by,
            )
            self._session.add(setting)
            await self._session.flush()
            return setting

        if existing.version != version:
            raise ValueError(
                f"version conflict: expected {existing.version} for key '{key}', got {version}"
            )
        existing.value = value
        existing.version = version + 1
        existing.updated_by = updated_by
        await self._session.flush()
        return existing
