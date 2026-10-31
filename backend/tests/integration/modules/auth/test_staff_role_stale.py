"""Staff role administration uses the current staff-user version."""

import os
import uuid

import pytest
from sqlalchemy import select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.auth.admin_service import (
    StaffAdminService,
    StaffStaleEditError,
)
from modest_chic_backend.modules.auth.models import Role, StaffUser

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_role_update_returns_new_version_and_rejects_stale_retry() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"role-actor-{suffix}@test.local", display_name="Owner")
                target = StaffUser(email=f"role-target-{suffix}@test.local", display_name="Staff")
                warehouse = await session.scalar(select(Role).where(Role.key == "warehouse"))
                session.add_all([actor, target])
                await session.flush()
                assert warehouse is not None
                original_version = target.updated_at
                service = StaffAdminService(session)
                updated = await service.set_roles(
                    target.id,
                    ["warehouse"],
                    actor.id,
                    original_version,
                )
                assert updated["roles"] == ["warehouse"]
                assert updated["updated_at"] != original_version.isoformat()
                with pytest.raises(StaffStaleEditError):
                    await service.set_roles(
                        target.id,
                        ["marketing"],
                        actor.id,
                        original_version,
                    )
                await session.rollback()
    finally:
        await database.dispose()
