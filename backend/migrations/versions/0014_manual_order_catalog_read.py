"""Allow order managers to read the catalog for manual order entry."""

from alembic import op
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modest_chic_backend.modules.auth.models import Permission, Role, role_permissions

revision = "0014_manual_order_catalog_read"
down_revision = "0013_customer_manage_permission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    permission = Permission.__table__
    permission_id = connection.execute(
        select(permission.c.id).where(permission.c.key == "catalog.read")
    ).scalar_one_or_none()
    if permission_id is None:
        raise RuntimeError("catalog.read permission must exist before granting it")
    roles = Role.__table__
    order_manager_id = connection.execute(
        select(roles.c.id).where(roles.c.key == "order_manager")
    ).scalar_one_or_none()
    if order_manager_id is None:
        raise RuntimeError("order_manager role must exist before catalog access is granted")
    connection.execute(
        pg_insert(role_permissions)
        .from_select(
            ["role_id", "permission_id"],
            select(literal(order_manager_id), literal(permission_id)),
        )
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    connection = op.get_bind()
    permission_id = connection.execute(
        select(Permission.id).where(Permission.key == "catalog.read")
    ).scalar_one_or_none()
    role_id = connection.execute(
        select(Role.id).where(Role.key == "order_manager")
    ).scalar_one_or_none()
    if permission_id is not None and role_id is not None:
        connection.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == permission_id,
            )
        )
