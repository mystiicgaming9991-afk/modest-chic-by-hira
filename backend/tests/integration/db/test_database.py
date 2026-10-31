import os

import pytest
from sqlalchemy import text

from modest_chic_backend.db.database import Database

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


@pytest.mark.asyncio
async def test_database_uses_independent_request_scoped_sessions() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])

    try:
        async with database.transaction() as session:
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
        async with database.session() as another_session:
            assert another_session is not session
            assert (await another_session.execute(text("SELECT 2"))).scalar_one() == 2
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_database_transaction_rolls_back_on_failure() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        with pytest.raises(RuntimeError, match="abort transaction"):
            async with database.transaction() as session:
                await session.execute(text("SELECT 1"))
                raise RuntimeError("abort transaction")
        async with database.session() as session:
            assert (await session.execute(text("SELECT 3"))).scalar_one() == 3
    finally:
        await database.dispose()
