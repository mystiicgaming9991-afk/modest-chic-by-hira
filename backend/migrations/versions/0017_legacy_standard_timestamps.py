"""Repair standard timestamps missing from early auth and audit schemas.

Revision ID: 0017_legacy_standard_timestamps
Revises: 0016_audit_updated_at
"""

from alembic import op

revision = "0017_legacy_standard_timestamps"
down_revision = "0016_audit_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure all early shared-base tables expose their standard update timestamp."""
    for table_name in (
        "roles",
        "permissions",
        "staff_sessions",
        "staff_invitations",
        "staff_password_resets",
        "audit_logs",
        "outbox_events",
    ):
        op.execute(
            f"ALTER TABLE {table_name} "
            "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        )


def downgrade() -> None:
    """Preserve compatibility columns because earlier table schemas vary by install age."""
