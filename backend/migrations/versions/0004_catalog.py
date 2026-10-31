"""Create catalog tables — products, variants, categories, collections, tags, media."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.catalog import models as catalog_models

_ = catalog_models

revision = "0004_catalog"
down_revision = "0003_audit_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the product_status enum and all 9 catalog tables."""
    # Create the enum type first
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE product_status AS ENUM ('DRAFT','PUBLISHED','ARCHIVED'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    tables = [
        catalog_models.Product.__table__,
        catalog_models.ProductVariant.__table__,
        catalog_models.Category.__table__,
        catalog_models.product_categories,
        catalog_models.Collection.__table__,
        catalog_models.collection_products,
        catalog_models.ProductTag.__table__,
        catalog_models.product_tag_links,
        catalog_models.ProductMedia.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    """Drop catalog tables and the product_status enum."""
    tables = [
        catalog_models.ProductMedia.__table__,
        catalog_models.product_tag_links,
        catalog_models.ProductTag.__table__,
        catalog_models.collection_products,
        catalog_models.Collection.__table__,
        catalog_models.product_categories,
        catalog_models.Category.__table__,
        catalog_models.ProductVariant.__table__,
        catalog_models.Product.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
    op.execute("DROP TYPE IF EXISTS product_status")
