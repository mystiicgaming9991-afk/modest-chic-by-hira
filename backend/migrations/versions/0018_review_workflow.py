"""Enforce one verified-purchase review and persist moderation reasons.

Revision ID: 0018_review_workflow
Revises: 0017_legacy_standard_timestamps
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_review_workflow"
down_revision = "0017_legacy_standard_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add moderation evidence and database-level review invariants."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("reviews")}
    if "moderation_reason" not in columns:
        op.add_column("reviews", sa.Column("moderation_reason", sa.Text(), nullable=True))

    check_names = {constraint["name"] for constraint in inspector.get_check_constraints("reviews")}
    if "chk_review_rating" not in check_names:
        op.create_check_constraint("chk_review_rating", "reviews", "rating BETWEEN 1 AND 5")
    if "chk_review_status" not in check_names:
        op.create_check_constraint(
            "chk_review_status", "reviews", "status IN ('PENDING', 'APPROVED', 'REJECTED')"
        )
    unique_names = {
        constraint["name"] for constraint in inspector.get_unique_constraints("reviews")
    }
    if "uq_review_order_item" not in unique_names:
        op.create_unique_constraint("uq_review_order_item", "reviews", ["order_item_id"])


def downgrade() -> None:
    """Remove review workflow constraints and moderation reason."""
    inspector = sa.inspect(op.get_bind())
    unique_names = {
        constraint["name"] for constraint in inspector.get_unique_constraints("reviews")
    }
    check_names = {constraint["name"] for constraint in inspector.get_check_constraints("reviews")}
    columns = {column["name"] for column in inspector.get_columns("reviews")}
    if "uq_review_order_item" in unique_names:
        op.drop_constraint("uq_review_order_item", "reviews", type_="unique")
    if "chk_review_status" in check_names:
        op.drop_constraint("chk_review_status", "reviews", type_="check")
    if "chk_review_rating" in check_names:
        op.drop_constraint("chk_review_rating", "reviews", type_="check")
    if "moderation_reason" in columns:
        op.drop_column("reviews", "moderation_reason")
