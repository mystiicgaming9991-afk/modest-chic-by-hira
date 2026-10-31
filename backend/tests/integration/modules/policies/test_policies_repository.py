"""Integration tests for policy versions repository with PostgreSQL."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.policies.models import PolicyVersion

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


async def _clean_policies(database: Database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(PolicyVersion))


@pytest.mark.asyncio
async def test_insert_and_retrieve_by_type() -> None:
    """A policy version can be inserted and retrieved by type."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_policies(database)
        async with database.transaction() as session:
            session.add(
                PolicyVersion(
                    type="returns",
                    version=1,
                    effective_from=datetime(2026, 1, 1, tzinfo=UTC),
                    content={"window_days": 7},
                    approved_by=None,
                )
            )
        async with database.session() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            versions = await repo.get_by_type("returns")
            assert len(versions) == 1
            assert versions[0].type == "returns"
            assert versions[0].version == 1
            assert versions[0].content == {"window_days": 7}
    finally:
        await _clean_policies(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_get_by_type_returns_empty_for_unknown_type() -> None:
    """An unknown policy type returns an empty list."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_policies(database)
        async with database.session() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            versions = await repo.get_by_type("nonexistent_type")
            assert versions == []
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_get_effective_returns_highest_version_before_now() -> None:
    """get_effective returns the highest version with effective_from <= now."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    now = datetime.now(UTC)
    try:
        await _clean_policies(database)
        async with database.transaction() as session:
            session.add_all(
                [
                    PolicyVersion(
                        type="terms",
                        version=1,
                        effective_from=now - timedelta(days=30),
                        content={"title": "Terms v1"},
                        approved_by=None,
                    ),
                    PolicyVersion(
                        type="terms",
                        version=2,
                        effective_from=now - timedelta(days=1),
                        content={"title": "Terms v2"},
                        approved_by=None,
                    ),
                ]
            )
        async with database.session() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            effective = await repo.get_effective("terms")
            assert effective is not None
            assert effective.version == 2
            assert effective.content == {"title": "Terms v2"}
    finally:
        await _clean_policies(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_get_effective_skips_future_dated() -> None:
    """A future-dated policy is not returned as effective."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    now = datetime.now(UTC)
    try:
        await _clean_policies(database)
        async with database.transaction() as session:
            session.add_all(
                [
                    PolicyVersion(
                        type="privacy",
                        version=1,
                        effective_from=now - timedelta(days=10),
                        content={"title": "Privacy v1"},
                        approved_by=None,
                    ),
                    PolicyVersion(
                        type="privacy",
                        version=2,
                        effective_from=now + timedelta(days=30),
                        content={"title": "Privacy v2 (future)"},
                        approved_by=None,
                    ),
                ]
            )
        async with database.session() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            effective = await repo.get_effective("privacy")
            assert effective is not None
            assert effective.version == 1  # v2 is future-dated
    finally:
        await _clean_policies(database)
        await database.dispose()


@pytest.mark.asyncio
async def test_get_effective_returns_none_for_no_versions() -> None:
    """When no versions exist for a type, get_effective returns None."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_policies(database)
        async with database.session() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            effective = await repo.get_effective("shipping")
            assert effective is None
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_auto_increment_version_on_insert() -> None:
    """Inserting a new policy version auto-increments the version number."""
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        await _clean_policies(database)
        async with database.transaction() as session:
            from modest_chic_backend.modules.policies.repository import PoliciesRepository

            repo = PoliciesRepository(session)
            v1 = await repo.insert(
                type="checkout_bundle",
                effective_from=datetime(2026, 1, 1, tzinfo=UTC),
                content={"checkout": "v1"},
                approved_by=None,
            )
            assert v1.version == 1
            v2 = await repo.insert(
                type="checkout_bundle",
                effective_from=datetime(2026, 2, 1, tzinfo=UTC),
                content={"checkout": "v2"},
                approved_by=None,
            )
            assert v2.version == 2
    finally:
        await _clean_policies(database)
        await database.dispose()
