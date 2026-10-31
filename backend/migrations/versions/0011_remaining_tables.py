"""Create remaining returns, refunds, settlements, reviews, notifications, and OTP tables."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.customers import models as cust
from modest_chic_backend.modules.notifications import models as notif
from modest_chic_backend.modules.refunds import models as refund
from modest_chic_backend.modules.returns import models as ret
from modest_chic_backend.modules.reviews import models as rev
from modest_chic_backend.modules.settlements import models as settle

_ = (cust, notif, refund, ret, rev, settle)

revision = "0011_remaining_tables"
down_revision = "0010_checkout_payment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [
        ret.Return.__table__,
        ret.ReturnItem.__table__,
        refund.Refund.__table__,
        settle.SettlementBatch.__table__,
        settle.SettlementLine.__table__,
        rev.Review.__table__,
        notif.Notification.__table__,
        cust.CustomerOtpChallenge.__table__,
        cust.CustomerSession.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [
        cust.CustomerSession.__table__,
        cust.CustomerOtpChallenge.__table__,
        notif.Notification.__table__,
        rev.Review.__table__,
        settle.SettlementLine.__table__,
        settle.SettlementBatch.__table__,
        refund.Refund.__table__,
        ret.ReturnItem.__table__,
        ret.Return.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
