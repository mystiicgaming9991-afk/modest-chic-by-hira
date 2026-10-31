"""Alembic environment for asynchronous PostgreSQL migrations."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.audit import models as audit_models
from modest_chic_backend.modules.auth import models as auth_models
from modest_chic_backend.modules.cart import models as cart_models
from modest_chic_backend.modules.catalog import models as catalog_models
from modest_chic_backend.modules.checkout import models as checkout_models
from modest_chic_backend.modules.coupons import models as coupons_models
from modest_chic_backend.modules.customers import models as customers_models
from modest_chic_backend.modules.fulfillment import models as fulfillment_models
from modest_chic_backend.modules.inventory import models as inventory_models
from modest_chic_backend.modules.notifications import models as notifications_models
from modest_chic_backend.modules.orders import models as orders_models
from modest_chic_backend.modules.outbox import models as outbox_models
from modest_chic_backend.modules.payments import models as payments_models
from modest_chic_backend.modules.policies import models as policies_models
from modest_chic_backend.modules.refunds import models as refunds_models
from modest_chic_backend.modules.returns import models as returns_models
from modest_chic_backend.modules.reviews import models as reviews_models
from modest_chic_backend.modules.settings import models as settings_models
from modest_chic_backend.modules.settlements import models as settlements_models

_ = (
    audit_models,
    auth_models,
    cart_models,
    catalog_models,
    checkout_models,
    coupons_models,
    customers_models,
    fulfillment_models,
    inventory_models,
    notifications_models,
    orders_models,
    payments_models,
    policies_models,
    refunds_models,
    returns_models,
    reviews_models,
    settings_models,
    settlements_models,
    outbox_models,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = None
if not config.attributes.get("database_url_explicit", False):
    database_url = (
        os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("TEST_DATABASE_URL")
    )
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL migrations without establishing a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: object) -> None:
    """Run Alembic operations on the synchronous connection facade."""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations through the configured async database driver."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_sync_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
