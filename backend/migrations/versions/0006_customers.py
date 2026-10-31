"""Create customer tables — customers, customer_addresses, customer_contact_consents."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.customers import models as cust_models

_ = cust_models

revision = "0006_customers"
down_revision = "0005_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [
        cust_models.Customer.__table__,
        cust_models.CustomerAddress.__table__,
        cust_models.CustomerContactConsent.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [
        cust_models.CustomerContactConsent.__table__,
        cust_models.CustomerAddress.__table__,
        cust_models.Customer.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
