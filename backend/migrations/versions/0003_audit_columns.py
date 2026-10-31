"""Add standard audit columns to every existing application table.

Each table receives the columns that it does not already have:
  - created_by  (UUID FK → staff_users, nullable)
  - updated_by  (UUID FK → staff_users, nullable)
  - deleted_at  (TIMESTAMPTZ, nullable)
  - deleted_by  (UUID FK → staff_users, nullable)

Columns that already exist (id, created_at, updated_at) are not touched.
"""

from alembic import op
from sqlalchemy import text

revision = "0003_audit_columns"
down_revision = "0002_commerce_foundation"
branch_labels = None
depends_on = None


_KIND = {
    "created_by": "uuid",
    "updated_by": "uuid",
    "deleted_at": "timestamptz",
    "deleted_by": "uuid",
}


def _add_if_missing(table_name: str, column: str, col_type: str) -> None:
    """Add *column* to *table_name* only when it does not already exist."""
    if column in _existing_columns(table_name):
        return
    sql = f"ALTER TABLE {table_name} ADD COLUMN {column} {col_type}"
    if column in {"created_by", "updated_by", "deleted_by"}:
        sql += " REFERENCES staff_users(id)"
    op.execute(sql)


def _existing_columns(table_name: str) -> set[str]:
    """Return lowercase column names currently on *table_name*."""
    conn = op.get_bind()
    rows = conn.execute(
        text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
        """),
        {"table_name": table_name},
    ).fetchall()
    return {row[0].lower() for row in rows}


def upgrade() -> None:
    """Add created_by, updated_by, deleted_at where missing on every app table."""
    tables = [
        "staff_users",
        "roles",
        "permissions",
        "staff_sessions",
        "staff_invitations",
        "staff_password_resets",
        "audit_logs",
        "outbox_events",
        "store_settings",
        "policy_versions",
    ]
    for table in tables:
        for column in ("created_by", "updated_by", "deleted_at", "deleted_by"):
            _add_if_missing(table, column, _KIND[column])


def downgrade() -> None:
    """Remove the newly added audit columns."""
    tables = [
        "staff_users",
        "roles",
        "permissions",
        "staff_sessions",
        "staff_invitations",
        "staff_password_resets",
        "audit_logs",
        "outbox_events",
        "store_settings",
        "policy_versions",
    ]
    for table in tables:
        for column in ("created_by", "updated_by", "deleted_at", "deleted_by"):
            op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")
