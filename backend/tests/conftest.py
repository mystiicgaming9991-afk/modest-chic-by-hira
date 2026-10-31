"""Shared PostgreSQL migration setup for integration tests."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis


@pytest.fixture(scope="session", autouse=True)
def migrate_application_test_database() -> None:
    """Upgrade the dedicated application test database before integration cases."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        return
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url_explicit"] = True
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def isolate_auth_rate_limits() -> None:
    """Prevent shared Redis test buckets from leaking between test cases."""
    redis_url = os.getenv("TEST_REDIS_URL")
    if redis_url is None:
        return

    async def clear_auth_rate_limit_keys() -> None:
        redis = Redis.from_url(redis_url, decode_responses=True)
        try:
            keys = await redis.keys("auth-rate-limit:*")
            if keys:
                await redis.delete(*keys)
        finally:
            await redis.aclose()

    asyncio.run(clear_auth_rate_limit_keys())
