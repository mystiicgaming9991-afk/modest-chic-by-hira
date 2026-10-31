"""Add stable idempotency and merchant reference to packed shipments."""

import sqlalchemy as sa
from alembic import op

revision = "0015_shipment_pack_identity"
down_revision = "0014_manual_order_catalog_read"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Revision 0010 creates fulfillment tables from live metadata, so fresh installs may already
    # have these columns and indexes while databases upgraded from older code do not.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("shipments")}
    if "idempotency_key" not in columns:
        op.add_column("shipments", sa.Column("idempotency_key", sa.String(length=255)))
    if "merchant_reference" not in columns:
        op.add_column("shipments", sa.Column("merchant_reference", sa.String(length=100)))

    indexes = {index["name"] for index in inspector.get_indexes("shipments")}
    if "uq_shipment_idempotency" not in indexes:
        op.create_index(
            "uq_shipment_idempotency",
            "shipments",
            ["idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )
    if "uq_shipment_merchant_reference" not in indexes:
        op.create_index(
            "uq_shipment_merchant_reference",
            "shipments",
            ["merchant_reference"],
            unique=True,
            postgresql_where=sa.text("merchant_reference IS NOT NULL"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("shipments")}
    indexes = {index["name"] for index in inspector.get_indexes("shipments")}
    if "uq_shipment_merchant_reference" in indexes:
        op.drop_index("uq_shipment_merchant_reference", table_name="shipments")
    if "uq_shipment_idempotency" in indexes:
        op.drop_index("uq_shipment_idempotency", table_name="shipments")
    if "merchant_reference" in columns:
        op.drop_column("shipments", "merchant_reference")
    if "idempotency_key" in columns:
        op.drop_column("shipments", "idempotency_key")
