"""Integration tests for settings module with PostgreSQL."""

import os
import uuid

import pytest
from sqlalchemy import delete, select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.settings.models import StoreSetting
from modest_chic_backend.modules.settings.service import SettingsService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


async def _clean(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(AuditLog))
        await session.execute(delete(StoreSetting))


async def _actor(database: Database, actor_id: uuid.UUID) -> None:
    async with database.transaction() as session:
        session.add(
            StaffUser(
                id=actor_id, email=f"setting-{actor_id}@test.local", display_name="Setting Test"
            )
        )


async def _remove_actor(database: Database, actor_id: uuid.UUID) -> None:
    async with database.transaction() as session:
        await session.execute(delete(StaffUser).where(StaffUser.id == actor_id))


@pytest.mark.asyncio
async def test_update_setting_produces_audit_log() -> None:
    """Updating a setting creates an audit record in the same transaction."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean(database)
        actor_id = uuid.uuid4()
        await _actor(database, actor_id)
        encryption_key = b"k" * 32

        # First create the setting
        async with database.transaction() as session:
            session.add(
                StoreSetting(
                    key="checkout.guest_allowed",
                    value=False,
                    is_secret=False,
                    version=1,
                )
            )

        # Now update it through the service
        async with database.transaction() as session:
            service = SettingsService(session, encryption_key)
            result = await service.update_setting(
                key="checkout.guest_allowed",
                value=True,
                version=1,
                actor_id=actor_id,
            )
            assert result.value is True
            assert result.version == 2

        # Verify audit log was created
        async with database.session() as session:
            audit_rows = (await session.execute(select(AuditLog))).scalars().all()
            assert any(
                row.action == "settings.updated"
                and row.entity_type == "store_setting"
                and row.actor_id == actor_id
                for row in audit_rows
            )
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_update_secret_round_trip_with_decrypt() -> None:
    """A secret value can be written, masked in list, and decrypted."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean(database)
        actor_id = uuid.uuid4()
        await _actor(database, actor_id)
        encryption_key = b"s" * 32

        # Write secret
        async with database.transaction() as session:
            service = SettingsService(session, encryption_key)
            await service.update_secret(
                key="provider.resend_api_key",
                value="re_live_key_123",
                version=1,
                actor_id=actor_id,
            )

        # List masks the secret
        async with database.session() as session:
            service = SettingsService(session, encryption_key)
            items = await service.get_all_visible()
            secret = next(item for item in items if item.key == "provider.resend_api_key")
            assert secret.value == "***"

        # Decrypt returns original
        async with database.session() as session:
            service = SettingsService(session, encryption_key)
            decrypted = await service.get_decrypted_secret(
                key="provider.resend_api_key",
                actor_id=actor_id,
            )
            assert decrypted["value"] == "re_live_key_123"
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()
