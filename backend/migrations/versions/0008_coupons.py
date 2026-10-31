"""Create coupon tables — coupons, coupon_scopes, coupon_redemptions."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.coupons import models as cmod

_ = cmod

revision = "0008_coupons"
down_revision = "0007_cart"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for enum_name, values in [
        ("coupon_type", ["FIXED", "PERCENT"]),
        ("coupon_state", ["ACTIVE", "PAUSED", "EXPIRED"]),
        ("coupon_redemption_status", ["RESERVED", "CONSUMED", "RELEASED", "EXPIRED"]),
    ]:
        vals = ",".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {enum_name} AS ENUM ({vals}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    tables = [cmod.Coupon.__table__, cmod.CouponScope.__table__, cmod.CouponRedemption.__table__]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [cmod.CouponRedemption.__table__, cmod.CouponScope.__table__, cmod.Coupon.__table__]
    for table in tables:
        op.drop_table(table.name)
    for t in ["coupon_redemption_status", "coupon_state", "coupon_type"]:
        op.execute(f"DROP TYPE IF EXISTS {t}")
