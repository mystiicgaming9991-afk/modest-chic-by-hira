"""Repair the audit timestamp on databases created by earlier model revisions.

Revision ID: 0016_audit_updated_at
Revises: 0015_shipment_pack_identity
"""

from alembic import op

revision = "0016_audit_updated_at"
down_revision = "0015_shipment_pack_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure the legacy audit table matches the append-only audit ORM model."""
    op.execute(
        "ALTER TABLE audit_logs "
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    )


def downgrade() -> None:
    """Keep the compatibility column on downgrade to avoid dropping existing data."""
