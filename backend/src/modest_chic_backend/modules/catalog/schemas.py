"""Pydantic request/response schemas for catalog administration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modest_chic_backend.modules.catalog.enums import ProductStatus

# ── Products ──────────────────────────────────────────────────────


class VariantCreate(BaseModel):
    """Request body for creating a variant alongside a product."""

    sku: str = Field(min_length=1, max_length=100)
    color_name: str = Field(min_length=1, max_length=255)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    dimensions: str | None = None
    weight_grams: int | None = None
    price_minor: int = Field(ge=0)
    sale_price_minor: int | None = Field(default=None, ge=0)


class ProductCreate(BaseModel):
    """Request body for creating a product with optional initial variants."""

    slug: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    fabric: str | None = None
    care: str | None = None
    dimensions: str | None = None
    variants: list[VariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Request body for updating product fields."""

    expected_updated_at: datetime
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    fabric: str | None = None
    care: str | None = None
    dimensions: str | None = None
    status: ProductStatus | None = None


class ProductRead(BaseModel):
    """Response body for a product without nested variants."""

    id: UUID
    slug: str
    title: str
    description: str | None
    fabric: str | None
    care: str | None
    dimensions: str | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VariantRead(BaseModel):
    """Response body for a product variant."""

    id: UUID
    product_id: UUID
    sku: str
    color_name: str
    color_hex: str | None
    dimensions: str | None
    weight_grams: int | None
    price_minor: int
    sale_price_minor: int | None
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MediaRead(BaseModel):
    """Response body for a media record."""

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    object_key: str
    media_type: str
    alt_text: str | None
    width: int | None
    height: int | None
    sort_order: int
    is_primary: bool
    status: ProductStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductDetail(BaseModel):
    """Response body for a product with nested variants and media."""

    id: UUID
    slug: str
    title: str
    description: str | None
    fabric: str | None
    care: str | None
    dimensions: str | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    variants: list[VariantRead] = Field(default_factory=list)
    media: list[MediaRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Paginated product list."""

    items: list[ProductRead]
    next_cursor: str | None = None


class VariantUpdate(BaseModel):
    """Request body for updating variant fields."""

    expected_updated_at: datetime
    color_name: str | None = None
    color_hex: str | None = None
    dimensions: str | None = None
    weight_grams: int | None = None
    price_minor: int | None = Field(default=None, ge=0)
    sale_price_minor: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ── Categories ────────────────────────────────────────────────────


class CategoryCreate(BaseModel):
    """Request body for creating a category."""

    slug: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    parent_id: UUID | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    """Request body for updating a category."""

    expected_updated_at: datetime
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    sort_order: int | None = None
    status: ProductStatus | None = None


class CategoryRead(BaseModel):
    """Response body for a category (self-referencing for tree)."""

    id: UUID
    slug: str
    name: str
    description: str | None
    parent_id: UUID | None
    sort_order: int
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    children: list["CategoryRead"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    """Wrapper for category list."""

    items: list[CategoryRead]


class ProductCategoriesUpdate(BaseModel):
    """Request body for replacing a product's ordered category memberships."""

    expected_updated_at: datetime
    category_ids: list[UUID] = Field(default_factory=list)


class ProductTagsUpdate(BaseModel):
    """Request body for replacing a product's tag memberships."""

    expected_updated_at: datetime
    tag_ids: list[UUID] = Field(default_factory=list)


# ── Collections ───────────────────────────────────────────────────


class CollectionCreate(BaseModel):
    """Request body for creating a collection."""

    slug: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CollectionUpdate(BaseModel):
    """Request body for updating a collection."""

    expected_updated_at: datetime
    name: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CollectionRead(BaseModel):
    """Response body for a collection."""

    id: UUID
    slug: str
    name: str
    description: str | None
    status: ProductStatus
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    """Wrapper for collection list."""

    items: list[CollectionRead]


class CollectionProductsUpdate(BaseModel):
    """Request body for setting product membership order."""

    expected_updated_at: datetime
    product_ids: list[UUID] = Field(default_factory=list)


# ── Tags ──────────────────────────────────────────────────────────


class TagCreate(BaseModel):
    """Request body for creating a tag."""

    name: str = Field(min_length=1, max_length=100)


class TagRead(BaseModel):
    """Response body for a tag."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    """Wrapper for tag list."""

    items: list[TagRead]


# ── Media ─────────────────────────────────────────────────────────


class MediaCreate(BaseModel):
    """Request body for attaching a media record."""

    object_key: str = Field(min_length=1, max_length=500)
    media_type: str = Field(min_length=1, max_length=50)
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    sort_order: int = 0
    is_primary: bool = False
    variant_id: UUID | None = None
