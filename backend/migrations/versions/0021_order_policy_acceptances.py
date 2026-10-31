"""Record every approved policy version accepted with an order.

Revision ID: 0021_order_policy_acceptances
Revises: 0020_builtin_role_grants
"""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.orders.models import OrderPolicyAcceptance

revision = "0021_order_policy_acceptances"
down_revision = "0020_builtin_role_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the immutable order-to-policy acceptance links."""
    Base.metadata.create_all(bind=op.get_bind(), tables=[OrderPolicyAcceptance.__table__])


def downgrade() -> None:
    """Remove only the order policy acceptance table."""
    op.drop_table(OrderPolicyAcceptance.__tablename__)
