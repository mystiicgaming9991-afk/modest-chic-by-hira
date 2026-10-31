import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("MIGRATION_DATABASE_URL"),
    reason="MIGRATION_DATABASE_URL is required for migration tests",
)


def alembic_config() -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", os.environ["MIGRATION_DATABASE_URL"])
    config.attributes["database_url_explicit"] = True
    return config


@pytest.mark.asyncio
async def test_migration_upgrade_and_downgrade_recreate_auth_schema() -> None:
    config = alembic_config()
    await _drop_migration_objects()

    await asyncio.to_thread(command.upgrade, config, "0001_staff_auth")
    initial_engine = create_async_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        async with initial_engine.connect() as connection:
            initial_tables = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
        assert "staff_users" in initial_tables
        assert "products" not in initial_tables
        assert "orders" not in initial_tables
    finally:
        await initial_engine.dispose()

    await asyncio.to_thread(command.upgrade, config, "head")
    engine = create_async_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
            owner_count = await connection.scalar(
                text("SELECT count(*) FROM roles WHERE key = 'owner'")
            )
            permission_count = await connection.scalar(text("SELECT count(*) FROM permissions"))
            manager_permission_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM role_permissions rp "
                    "JOIN roles r ON r.id = rp.role_id WHERE r.key = 'order_manager'"
                )
            )
            built_in_grants = set(
                (
                    await connection.execute(
                        text(
                            "SELECT r.key, p.key FROM role_permissions rp "
                            "JOIN roles r ON r.id = rp.role_id "
                            "JOIN permissions p ON p.id = rp.permission_id"
                        )
                    )
                ).all()
            )
        assert {
            "staff_users",
            "staff_sessions",
            "staff_invitations",
            "staff_password_resets",
            "audit_logs",
            "outbox_events",
        } <= table_names
        assert owner_count == 1
        assert permission_count >= 20
        assert manager_permission_count > 0
        assert {
            ("order_manager", "catalog.read"),
            ("warehouse", "inventory.read"),
            ("warehouse", "inventory.thresholds.manage"),
            ("customer_support", "customer.manage"),
            ("marketing", "dashboard.read"),
        } <= built_in_grants
    finally:
        await engine.dispose()

    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")


async def _drop_migration_objects() -> None:
    engine = create_async_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql("DROP SCHEMA public CASCADE")
            await connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        await engine.dispose()
