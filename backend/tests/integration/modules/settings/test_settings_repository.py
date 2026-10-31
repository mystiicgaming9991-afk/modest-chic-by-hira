"""Integration tests for store settings repository with PostgreSQL."""

import os

import pytest
from sqlalchemy import delete

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.settings.models import StoreSetting

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


async def _clean_settings(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(StoreSetting))


@pytest.mark.asyncio
async def test_create_and_read_setting() -> None:
    """A setting can be created and read back by key."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.transaction() as session:
            session.add(
                StoreSetting(
                    key="test.key",
                    value={"enabled": True},
                    is_secret=False,
                    version=1,
                )
            )
        async with database.session() as session:
            # Will be populated after repository exists
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            setting = await repo.get_by_key("test.key")
            assert setting is not None
            assert setting.key == "test.key"
            assert setting.value == {"enabled": True}
            assert setting.version == 1
    finally:
        await _clean_settings(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_get_by_key_returns_none_for_missing_key() -> None:
    """A missing key returns None."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.session() as session:
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            setting = await repo.get_by_key("nonexistent.key")
            assert setting is None
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_upsert_creates_new_setting() -> None:
    """Upsert creates a new setting when the key does not exist."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.transaction() as session:
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            created = await repo.upsert_with_version_check(
                key="new.key",
                value={"max": 100},
                version=1,
                updated_by=None,
            )
            assert created.key == "new.key"
            assert created.value == {"max": 100}
            assert created.version == 2  # increment on write
    finally:
        await _clean_settings(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_upsert_updates_existing_with_correct_version() -> None:
    """Upsert updates when the version matches."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.transaction() as session:
            session.add(
                StoreSetting(
                    key="existing.key",
                    value={"count": 1},
                    is_secret=False,
                    version=1,
                )
            )
        async with database.transaction() as session:
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            updated = await repo.upsert_with_version_check(
                key="existing.key",
                value={"count": 2},
                version=1,  # matches stored version
                updated_by=None,
            )
            assert updated.value == {"count": 2}
            assert updated.version == 2
    finally:
        await _clean_settings(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_upsert_rejects_stale_version() -> None:
    """Upsert raises when the version in the request does not match stored."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.transaction() as session:
            session.add(
                StoreSetting(
                    key="stale.key",
                    value={"count": 1},
                    is_secret=False,
                    version=5,
                )
            )
        async with database.transaction() as session:
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            with pytest.raises(ValueError, match="version conflict"):
                await repo.upsert_with_version_check(
                    key="stale.key",
                    value={"count": 99},
                    version=3,  # stale
                    updated_by=None,
                )
    finally:
        await _clean_settings(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_get_all_returns_all_non_secret_settings() -> None:
    """get_all returns all settings; secret masking is done in the service."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_settings(database)
        async with database.transaction() as session:
            session.add_all(
                [
                    StoreSetting(key="a", value={"x": 1}, is_secret=False, version=1),
                    StoreSetting(key="b", value={"y": 2}, is_secret=True, version=1),
                ]
            )
        async with database.session() as session:
            from modest_chic_backend.modules.settings.repository import SettingsRepository

            repo = SettingsRepository(session)
            items = await repo.get_all()
            keys = {item.key for item in items}
            assert "a" in keys
            assert "b" in keys  # The repository returns all; service masks secrets
            assert len(items) >= 2
    finally:
        await _clean_settings(database)
        await database.dispose()
