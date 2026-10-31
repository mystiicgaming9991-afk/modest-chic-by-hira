"""Create checkout/payment/fulfillment tables."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.checkout import models as chk
from modest_chic_backend.modules.fulfillment import models as ful
from modest_chic_backend.modules.payments import models as pay

_ = (chk, ful, pay)

revision = "0010_checkout_payment"
down_revision = "0009_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [
        chk.OrderAccessToken.__table__,
        pay.Payment.__table__,
        pay.PaymentEvent.__table__,
        ful.Shipment.__table__,
        ful.ShipmentItem.__table__,
        ful.ShipmentEvent.__table__,
        ful.Pickup.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [
        ful.Pickup.__table__,
        ful.ShipmentEvent.__table__,
        ful.ShipmentItem.__table__,
        ful.Shipment.__table__,
        pay.PaymentEvent.__table__,
        pay.Payment.__table__,
        chk.OrderAccessToken.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
