"""Create inventory tables — locations, balances, reservations, movements."""

from alembic import op

from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.inventory import models as inv_models

_ = inv_models

revision = "0005_inventory"
down_revision = "0004_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create reservation_status and movement_reason enums, then all inventory tables."""
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE reservation_status AS ENUM ('ACTIVE','CONSUMED','RELEASED','EXPIRED'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE movement_reason AS ENUM ("
        "'RECEIVE','ADJUST','RESERVE','RELEASE','CONSUME','EXPIRE','RESTOCK'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    tables = [
        inv_models.InventoryLocation.__table__,
        inv_models.InventoryBalance.__table__,
        inv_models.InventoryReservation.__table__,
        inv_models.InventoryMovement.__table__,
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)

    # Seed default location
    op.execute(
        "INSERT INTO inventory_locations (key, name) VALUES ('main', 'Main Warehouse') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    tables = [
        inv_models.InventoryMovement.__table__,
        inv_models.InventoryReservation.__table__,
        inv_models.InventoryBalance.__table__,
        inv_models.InventoryLocation.__table__,
    ]
    for table in tables:
        op.drop_table(table.name)
    op.execute("DROP TYPE IF EXISTS movement_reason")
    op.execute("DROP TYPE IF EXISTS reservation_status")
