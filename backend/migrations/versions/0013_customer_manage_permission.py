"""Grant explicit staff capability for customer profile changes."""

import uuid

from alembic import op
from sqlalchemy import delete, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modest_chic_backend.modules.auth.models import Permission, Role, role_permissions

revision = "0013_customer_manage_permission"
down_revision = "0012_customer_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    permission = Permission.__table__
    permission_id = uuid.uuid5(uuid.NAMESPACE_URL, "modest-chic:permission:customer.manage")
    connection.execute(
        pg_insert(permission)
        .values(
            id=permission_id,
            key="customer.manage",
            description="Customer profile manage",
        )
        .on_conflict_do_nothing(index_elements=["key"])
    )
    actual_permission_id = connection.execute(
        select(permission.c.id).where(permission.c.key == "customer.manage")
    ).scalar_one()
    roles = Role.__table__
    available_roles = set(
        connection.execute(
            select(roles.c.key).where(roles.c.key.in_(["owner", "customer_support"]))
        ).scalars()
    )
    connection.execute(
        pg_insert(role_permissions)
        .from_select(
            ["role_id", "permission_id"],
            select(roles.c.id, literal(actual_permission_id)).where(
                roles.c.key.in_(["owner", "customer_support"])
            ),
        )
        .on_conflict_do_nothing()
    )
    if available_roles != {"owner", "customer_support"}:
        raise RuntimeError("owner and customer_support roles must exist")
    if actual_permission_id is None:
        raise RuntimeError("customer.manage permission could not be created")


def downgrade() -> None:
    connection = op.get_bind()
    permission = Permission.__table__
    permission_id = connection.execute(
        select(permission.c.id).where(permission.c.key == "customer.manage")
    ).scalar_one_or_none()
    if permission_id is not None:
        connection.execute(
            delete(role_permissions).where(role_permissions.c.permission_id == permission_id)
        )
        connection.execute(delete(permission).where(permission.c.id == permission_id))
