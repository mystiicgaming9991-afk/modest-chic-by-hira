"""Add verified customer accounts and bounded OTP challenges."""

import sqlalchemy as sa
from alembic import op

from modest_chic_backend.modules.customers.models import CustomerAccount

revision = "0012_customer_accounts"
down_revision = "0011_remaining_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Revision 0011 builds this table from live model metadata. A fresh install
    # can already have these columns, while an older installation will not.
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("customer_otp_challenges")
    }
    if "superseded_at" not in columns:
        op.add_column(
            "customer_otp_challenges", sa.Column("superseded_at", sa.DateTime(timezone=True))
        )
    if "failed_attempts" not in columns:
        op.add_column(
            "customer_otp_challenges",
            sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        )
    CustomerAccount.__table__.create(bind=op.get_bind())


def downgrade() -> None:
    CustomerAccount.__table__.drop(bind=op.get_bind())
    op.drop_column("customer_otp_challenges", "failed_attempts")
    op.drop_column("customer_otp_challenges", "superseded_at")
