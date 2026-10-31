"""Integration tests for policies module with PostgreSQL."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from json import loads
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from modest_chic_backend.api.v1.policies import public_effective_policy
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.policies.models import PolicyVersion
from modest_chic_backend.modules.policies.service import PoliciesService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


async def _clean(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(AuditLog))
        await session.execute(delete(PolicyVersion))


async def _actor(database: Database, actor_id: uuid.UUID) -> None:
    async with database.transaction() as session:
        session.add(
            StaffUser(
                id=actor_id, email=f"policy-{actor_id}@test.local", display_name="Policy Test"
            )
        )


async def _remove_actor(database: Database, actor_id: uuid.UUID) -> None:
    async with database.transaction() as session:
        await session.execute(delete(StaffUser).where(StaffUser.id == actor_id))


@pytest.mark.asyncio
async def test_publish_policy_produces_audit_log() -> None:
    """Publishing a policy creates an audit record."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean(database)
        actor_id = uuid.uuid4()
        await _actor(database, actor_id)

        async with database.transaction() as session:
            service = PoliciesService(session)
            result = await service.publish_version(
                type="returns",
                effective_from=datetime.now(UTC),
                content={"window_days": 7},
                approved_by=actor_id,
            )
            assert result.version == 1

        # Verify audit log
        async with database.session() as session:
            audit_rows = (await session.execute(select(AuditLog))).scalars().all()
            assert any(
                row.action == "policy.published"
                and row.entity_type == "policy_version"
                and row.actor_id == actor_id
                for row in audit_rows
            )
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_policy_version_auto_increments() -> None:
    """Multiple policy versions auto-increment version numbers."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean(database)
        actor_id = uuid.uuid4()
        await _actor(database, actor_id)
        now = datetime.now(UTC)

        async with database.transaction() as session:
            service = PoliciesService(session)
            v1 = await service.publish_version(
                type="terms",
                effective_from=now - timedelta(days=10),
                content={"title": "Terms v1"},
                approved_by=actor_id,
            )
            assert v1.version == 1

        async with database.transaction() as session:
            service = PoliciesService(session)
            v2 = await service.publish_version(
                type="terms",
                effective_from=now,
                content={"title": "Terms v2"},
                approved_by=actor_id,
            )
            assert v2.version == 2

        # Verify effective is v2
        async with database.session() as session:
            service = PoliciesService(session)
            effective = await service.get_effective("terms")
            assert effective is not None
            assert effective.version == 2
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_future_dated_policy_not_effective() -> None:
    """A future-dated policy is not returned as effective."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean(database)
        actor_id = uuid.uuid4()
        await _actor(database, actor_id)
        now = datetime.now(UTC)

        async with database.transaction() as session:
            service = PoliciesService(session)
            await service.publish_version(
                type="privacy",
                effective_from=now - timedelta(days=5),
                content={"title": "Privacy v1"},
                approved_by=actor_id,
            )
            await service.publish_version(
                type="privacy",
                effective_from=now + timedelta(days=30),
                content={"title": "Privacy v2 (future)"},
                approved_by=actor_id,
            )

        async with database.session() as session:
            service = PoliciesService(session)
            effective = await service.get_effective("privacy")
            assert effective is not None
            assert effective.version == 1  # v2 is future
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_public_policy_returns_only_the_current_effective_approved_version() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    actor_id = uuid.uuid4()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
    try:
        await _clean(database)
        await _actor(database, actor_id)
        now = datetime.now(UTC)
        async with database.transaction() as session:
            service = PoliciesService(session)
            await service.publish_version(
                type="shipping",
                effective_from=now - timedelta(days=1),
                content={"delivery": "Current approved delivery terms"},
                approved_by=actor_id,
            )
            await service.publish_version(
                type="shipping",
                effective_from=now + timedelta(days=1),
                content={"delivery": "Future delivery terms"},
                approved_by=actor_id,
            )

        response = await public_effective_policy("shipping", request)  # type: ignore[arg-type]
        assert response.status_code == 200
        assert loads(response.body) == {
            "type": "shipping",
            "version": 1,
            "content": {"delivery": "Current approved delivery terms"},
        }

        with pytest.raises(ApplicationError) as unpublished_policy:
            await public_effective_policy("returns", request)  # type: ignore[arg-type]
        assert unpublished_policy.value.status_code == 404
        with pytest.raises(ApplicationError) as private_policy_type:
            await public_effective_policy("checkout_bundle", request)  # type: ignore[arg-type]
        assert private_policy_type.value.status_code == 404
    finally:
        await _clean(database)
        await _remove_actor(database, actor_id)
        await database.dispose()
