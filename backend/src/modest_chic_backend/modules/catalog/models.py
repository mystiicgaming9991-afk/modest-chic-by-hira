"""Catalog persistence models — products, variants, categories, collections, tags, and media.

All entities inherit :class:`BaseModel` for standard audit columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modest_chic_backend.db.base import Base, BaseModel
from modest_chic_backend.modules.catalog.enums import ProductStatus

# ── Through tables ────────────────────────────────────────────────


product_categories = Table(
    "product_categories",
    Base.metadata,
    Column(
        "product_id",
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("sort_order", Integer, nullable=False, server_default=text("0")),
)

collection_products = Table(
    "collection_products",
    Base.metadata,
    Column(
        "collection_id",
        Uuid(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "product_id",
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("sort_order", Integer, nullable=False, server_default=text("0")),
)

product_tag_links = Table(
    "product_tag_links",
    Base.metadata,
    Column(
        "product_id",
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        Uuid(as_uuid=True),
        ForeignKey("product_tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ── Entities ──────────────────────────────────────────────────────


class Product(BaseModel):
    """A sellable fashion item with draft/published/archived lifecycle."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("length(trim(slug)) > 0", name="chk_product_slug_not_blank"),
        CheckConstraint("length(trim(title)) > 0", name="chk_product_title_not_blank"),
        Index("uq_product_slug", "slug", unique=True),
        Index("idx_product_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    fabric: Mapped[str | None] = mapped_column(String(255))
    care: Mapped[str | None] = mapped_column(Text)
    dimensions: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=True),
        nullable=False,
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    media: Mapped[list["ProductMedia"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(BaseModel):
    """A sellable SKU under a product with price, color, and dimensions."""

    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("length(trim(sku)) > 0", name="chk_variant_sku_not_blank"),
        CheckConstraint("price_minor >= 0", name="chk_variant_price_nonnegative"),
        CheckConstraint(
            "sale_price_minor IS NULL OR sale_price_minor <= price_minor",
            name="chk_sale_price",
        ),
        Index("uq_variant_sku", "sku", unique=True),
        Index("idx_variant_product", "product_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    color_name: Mapped[str] = mapped_column(String(255), nullable=False)
    color_hex: Mapped[str | None] = mapped_column(CHAR(7))
    dimensions: Mapped[str | None] = mapped_column(String(255))
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    sale_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="PKR", server_default="PKR"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    product: Mapped["Product"] = relationship(back_populates="variants")


class Category(BaseModel):
    """A hierarchical product grouping with a unique slug."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("length(trim(slug)) > 0", name="chk_category_slug_not_blank"),
        Index("uq_category_slug", "slug", unique=True),
        Index("idx_category_parent", "parent_id"),
    )

    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=True),
        nullable=False,
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
    )


class Collection(BaseModel):
    """A curated, ordered set of products with optional scheduling."""

    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint("length(trim(slug)) > 0", name="chk_collection_slug_not_blank"),
        Index("uq_collection_slug", "slug", unique=True),
    )

    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=True),
        nullable=False,
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductTag(BaseModel):
    """A lightweight label shared across products."""

    __tablename__ = "product_tags"
    __table_args__ = (Index("uq_tag_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ProductMedia(BaseModel):
    """An image or video record linked to a product (and optionally a variant)."""

    __tablename__ = "product_media"
    __table_args__ = (
        Index("idx_media_product", "product_id"),
        Index("idx_media_variant", "variant_id", postgresql_where=text("variant_id IS NOT NULL")),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(50), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(500))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=True),
        nullable=False,
        default=ProductStatus.PUBLISHED,
        server_default=ProductStatus.PUBLISHED.value,
    )

    product: Mapped["Product"] = relationship(back_populates="media")


__all__ = [
    "Category",
    "Collection",
    "Product",
    "ProductMedia",
    "ProductTag",
    "ProductVariant",
    "collection_products",
    "product_categories",
    "product_tag_links",
]
