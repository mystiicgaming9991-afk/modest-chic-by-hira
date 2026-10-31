"""Restore all documented grants for built-in staff roles.

Revision ID: 0020_builtin_role_grants
Revises: 0019_low_stock_thresholds
"""

from alembic import op
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modest_chic_backend.modules.auth.models import Permission, Role, role_permissions

revision = "0020_builtin_role_grants"
down_revision = "0019_low_stock_thresholds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Insert missing grants without removing intentional role assignments."""
    grants_by_role = {
        "owner": {
            "dashboard.read",
            "catalog.read",
            "catalog.write",
            "catalog.archive",
            "inventory.read",
            "inventory.adjust",
            "inventory.receive",
            "inventory.inspect",
            "inventory.thresholds.manage",
            "order.read",
            "order.create_manual",
            "order.confirm",
            "order.cancel",
            "fulfillment.pack",
            "fulfillment.book",
            "fulfillment.handoff",
            "customer.read",
            "customer.manage",
            "customer.export",
            "payment.read",
            "refund.request",
            "refund.approve",
            "settlement.read",
            "settlement.import",
            "settlement.reconcile",
            "promotion.read",
            "promotion.write",
            "review.moderate",
            "staff.manage",
            "settings.manage",
            "audit.read",
            "notification.read",
            "analytics.read",
        },
        "order_manager": {
            "dashboard.read",
            "catalog.read",
            "order.read",
            "order.create_manual",
            "order.confirm",
            "order.cancel",
            "fulfillment.pack",
            "fulfillment.book",
            "fulfillment.handoff",
            "customer.read",
            "payment.read",
            "refund.request",
            "review.moderate",
            "notification.read",
            "analytics.read",
        },
        "warehouse": {
            "dashboard.read",
            "inventory.read",
            "inventory.adjust",
            "inventory.receive",
            "inventory.inspect",
            "inventory.thresholds.manage",
            "order.read",
            "fulfillment.pack",
            "fulfillment.book",
            "fulfillment.handoff",
        },
        "customer_support": {
            "dashboard.read",
            "order.read",
            "customer.read",
            "customer.manage",
            "refund.request",
            "review.moderate",
            "notification.read",
        },
        "marketing": {
            "dashboard.read",
            "catalog.read",
            "promotion.read",
            "promotion.write",
            "review.moderate",
            "analytics.read",
        },
    }

    connection = op.get_bind()
    roles = Role.__table__
    permissions = Permission.__table__
    role_ids = dict(
        connection.execute(
            select(roles.c.key, roles.c.id).where(roles.c.key.in_(grants_by_role))
        ).all()
    )
    permission_keys = set().union(*grants_by_role.values())
    permission_ids = dict(
        connection.execute(
            select(permissions.c.key, permissions.c.id).where(
                permissions.c.key.in_(permission_keys)
            )
        ).all()
    )
    if set(role_ids) != set(grants_by_role):
        raise RuntimeError("all built-in staff roles must exist before grants are repaired")
    if set(permission_ids) != permission_keys:
        missing = sorted(permission_keys - set(permission_ids))
        raise RuntimeError(f"built-in staff permissions are missing: {', '.join(missing)}")

    grants = [
        {"role_id": role_ids[role_key], "permission_id": permission_ids[permission_key]}
        for role_key, role_permission_keys in grants_by_role.items()
        for permission_key in sorted(role_permission_keys)
    ]
    connection.execute(pg_insert(role_permissions).values(grants).on_conflict_do_nothing())


def downgrade() -> None:
    """Keep the repaired built-in grants so a code rollback cannot lock staff out."""
