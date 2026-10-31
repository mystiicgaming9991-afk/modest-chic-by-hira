"""Create cart tables — carts, cart_items."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.cart import models as cart_models

_ = cart_models

revision = "0007_cart"
down_revision = "0006_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [cart_models.Cart.__table__, cart_models.CartItem.__table__]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [cart_models.CartItem.__table__, cart_models.Cart.__table__]
    for table in tables:
        op.drop_table(table.name)
