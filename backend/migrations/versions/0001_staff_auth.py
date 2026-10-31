"""Create staff authentication, audit, and outbox tables."""

import uuid

from alembic import op
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.audit import models as audit_models
from modest_chic_backend.modules.auth import models as auth_models
from modest_chic_backend.modules.outbox import models as outbox_models

_ = (audit_models, outbox_models)

revision = "0001_staff_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the complete initial auth schema and its PostgreSQL indexes."""
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[
            auth_models.StaffUser.__table__,
            auth_models.Role.__table__,
            auth_models.Permission.__table__,
            auth_models.staff_user_roles,
            auth_models.role_permissions,
            auth_models.StaffSession.__table__,
            auth_models.StaffInvitation.__table__,
            auth_models.StaffPasswordReset.__table__,
            audit_models.AuditLog.__table__,
            outbox_models.OutboxEvent.__table__,
        ],
    )
    _seed_roles_and_permissions()


def downgrade() -> None:
    """Drop the auth-only schema in reverse dependency order."""
    for table in (
        outbox_models.OutboxEvent.__table__,
        audit_models.AuditLog.__table__,
        auth_models.StaffPasswordReset.__table__,
        auth_models.StaffInvitation.__table__,
        auth_models.StaffSession.__table__,
        auth_models.staff_user_roles,
        auth_models.role_permissions,
        auth_models.StaffUser.__table__,
        auth_models.Permission.__table__,
        auth_models.Role.__table__,
    ):
        op.drop_table(table.name)
    op.execute("DROP TYPE IF EXISTS staff_status")


def _seed_roles_and_permissions() -> None:
    """Create the documented staff roles and capability catalog idempotently."""
    connection = op.get_bind()
    roles = auth_models.Role.__table__
    permissions = auth_models.Permission.__table__
    role_permissions = auth_models.role_permissions
    role_rows = [
        {"id": _stable_id("role", key), "key": key, "display_label": label}
        for key, label in (
            ("owner", "Owner"),
            ("order_manager", "Order Manager"),
            ("warehouse", "Warehouse"),
            ("customer_support", "Customer Support"),
            ("marketing", "Marketing"),
        )
    ]
    permission_keys = (
        "dashboard.read",
        "catalog.read",
        "catalog.write",
        "catalog.archive",
        "inventory.read",
        "inventory.adjust",
        "inventory.receive",
        "inventory.inspect",
        "order.read",
        "order.create_manual",
        "order.confirm",
        "order.cancel",
        "fulfillment.pack",
        "fulfillment.book",
        "fulfillment.handoff",
        "customer.read",
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
    )
    permission_rows = [
        {
            "id": _stable_id("permission", key),
            "key": key,
            "description": key.replace(".", " ").replace("_", " ").capitalize(),
        }
        for key in permission_keys
    ]
    connection.execute(
        insert(roles).values(role_rows).on_conflict_do_nothing(index_elements=["key"])
    )
    connection.execute(
        insert(permissions).values(permission_rows).on_conflict_do_nothing(index_elements=["key"])
    )
    role_id_by_key = dict(connection.execute(select(roles.c.key, roles.c.id)).all())
    permission_id_by_key = dict(
        connection.execute(select(permissions.c.key, permissions.c.id)).all()
    )
    grants_by_role = {
        "owner": set(permission_keys),
        "order_manager": {
            "dashboard.read",
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
            "order.read",
            "fulfillment.pack",
            "fulfillment.book",
            "fulfillment.handoff",
        },
        "customer_support": {
            "dashboard.read",
            "order.read",
            "customer.read",
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
    grants = [
        {
            "role_id": role_id_by_key[role_key],
            "permission_id": permission_id_by_key[permission_key],
        }
        for role_key, permission_keys_for_role in grants_by_role.items()
        for permission_key in permission_keys_for_role
    ]
    connection.execute(insert(role_permissions).values(grants).on_conflict_do_nothing())


def _stable_id(entity: str, key: str) -> uuid.UUID:
    """Return a stable UUID so role seeding remains repeatable across environments."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"modest-chic:{entity}:{key}")
