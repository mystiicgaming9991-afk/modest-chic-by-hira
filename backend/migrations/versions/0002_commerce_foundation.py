"""Create store_settings and policy_versions tables for the commerce foundation."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.policies import models as policies_models
from modest_chic_backend.modules.settings import models as settings_models

_ = (settings_models, policies_models)

revision = "0002_commerce_foundation"
down_revision = "0001_staff_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create store_settings and policy_versions tables with their constraints and indexes."""
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[
            settings_models.StoreSetting.__table__,
            policies_models.PolicyVersion.__table__,
        ],
    )


def downgrade() -> None:
    """Drop the commerce foundation tables in reverse dependency order."""
    op.drop_table(policies_models.PolicyVersion.__tablename__)
    op.drop_table(settings_models.StoreSetting.__tablename__)
