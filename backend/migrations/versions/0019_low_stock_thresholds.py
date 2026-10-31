"""Add explicit per-balance low-stock alerts and capability.

Revision ID: 0019_low_stock_thresholds
Revises: 0018_review_workflow
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import delete, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modest_chic_backend.modules.auth.models import Permission, Role, role_permissions

revision = "0019_low_stock_thresholds"
down_revision = "0018_review_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable thresholds and grant their management to owner/warehouse."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("inventory_balances")}
    if "low_stock_threshold" not in columns:
        op.add_column(
            "inventory_balances",
            sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
        )
    checks = {item["name"] for item in inspector.get_check_constraints("inventory_balances")}
    if "chk_low_stock_threshold_nonnegative" not in checks:
        op.create_check_constraint(
            "chk_low_stock_threshold_nonnegative",
            "inventory_balances",
            "low_stock_threshold IS NULL OR low_stock_threshold >= 0",
        )

    permission = Permission.__table__
    permission_key = "inventory.thresholds.manage"
    permission_id = uuid.uuid5(uuid.NAMESPACE_URL, f"modest-chic:permission:{permission_key}")
    connection.execute(
        pg_insert(permission)
        .values(
            id=permission_id,
            key=permission_key,
            description="Inventory low-stock threshold management",
        )
        .on_conflict_do_nothing(index_elements=["key"])
    )
    actual_permission_id = connection.execute(
        select(permission.c.id).where(permission.c.key == permission_key)
    ).scalar_one()
    roles = Role.__table__
    role_names = ["owner", "warehouse"]
    available_roles = set(
        connection.execute(select(roles.c.key).where(roles.c.key.in_(role_names))).scalars()
    )
    if available_roles != set(role_names):
        raise RuntimeError("owner and warehouse roles must exist")
    connection.execute(
        pg_insert(role_permissions)
        .from_select(
            ["role_id", "permission_id"],
            select(roles.c.id, literal(actual_permission_id)).where(roles.c.key.in_(role_names)),
        )
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Remove the alert-management grant and optional threshold data."""
    connection = op.get_bind()
    permission = Permission.__table__
    permission_id = connection.execute(
        select(permission.c.id).where(permission.c.key == "inventory.thresholds.manage")
    ).scalar_one_or_none()
    if permission_id is not None:
        connection.execute(
            delete(role_permissions).where(role_permissions.c.permission_id == permission_id)
        )
        connection.execute(delete(permission).where(permission.c.id == permission_id))

    inspector = sa.inspect(connection)
    checks = {item["name"] for item in inspector.get_check_constraints("inventory_balances")}
    if "chk_low_stock_threshold_nonnegative" in checks:
        op.drop_constraint(
            "chk_low_stock_threshold_nonnegative", "inventory_balances", type_="check"
        )
    columns = {column["name"] for column in inspector.get_columns("inventory_balances")}
    if "low_stock_threshold" in columns:
        op.drop_column("inventory_balances", "low_stock_threshold")
