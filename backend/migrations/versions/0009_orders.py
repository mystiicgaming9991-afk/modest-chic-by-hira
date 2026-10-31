"""Create order tables — orders, order_items, order_events, order_notes."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.orders import models as omod

_ = omod

revision = "0009_orders"
down_revision = "0008_coupons"
branch_labels = None
depends_on = None

_ENUMS = {
    "order_source": ["STOREFRONT", "MANUAL", "SOCIAL"],
    "order_state": [
        "PENDING_CONFIRMATION",
        "CONFIRMED",
        "PROCESSING",
        "FULFILLED",
        "COMPLETED",
        "CANCELLED",
    ],
    "payment_method": ["COD", "ONLINE", "MANUAL"],
    "payment_state": ["PENDING", "AUTHORIZED", "PAID", "FAILED", "REFUNDED", "PARTIALLY_REFUNDED"],
    "fulfillment_method": ["DELIVERY", "PICKUP"],
}


def upgrade() -> None:
    for name, vals in _ENUMS.items():
        vlist = ",".join(f"'{v}'" for v in vals)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({vlist}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )
    tables = [
        omod.Order.__table__,
        omod.OrderItem.__table__,
        omod.OrderEvent.__table__,
        omod.OrderNote.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [
        omod.OrderNote.__table__,
        omod.OrderEvent.__table__,
        omod.OrderItem.__table__,
        omod.Order.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
    for name in reversed(list(_ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name}")
