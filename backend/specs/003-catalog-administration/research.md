# Research: Catalog Administration

**Feature**: 003-catalog-administration

## Decision 1: Product Status Enum

**Choice**: PostgreSQL native ENUM `product_status` with values `DRAFT`, `PUBLISHED`, `ARCHIVED`. Both products and categories share this type.

**Alternatives**: Separate enums per entity (unnecessary — lifecycle is identical).

## Decision 2: Price Storage

**Choice**: `price_minor` and `sale_price_minor` as INT columns in PKR paisa. API accepts/produces decimal strings like `"1500.00"` per shared conventions contract. Sale price constrained `<= price_minor`.

**Alternatives**: NUMERIC(12,2) (more bytes, harder to aggregate); separate price history table (overkill for MVP — current price is sufficient).

## Decision 3: Variant Deletion

**Choice**: `ON DELETE RESTRICT` on `product_variants.product_id`. Products with variants cannot be deleted — they must be archived. This preserves order history.

**Alternatives**: CASCADE (destroys order item references); SET NULL (corrupts existing orders).

## Decision 4: Media Upload

**Choice**: Media records store an S3 object key and metadata. Actual upload is outside the transaction boundary — the API validates the media record, the upload happens separately via presigned URLs (future Spec 021). For now, media records reference keys that deployment/recovery will handle.

**Alternatives**: Store media in DB (bloated, slow); store full URLs (fragile across environments).

## Decision 5: Tag Model

**Choice**: Separate `product_tags` table with M:N through `product_tag_links`. Tags are pre-created and shared across products.

**Alternatives**: JSONB array on products (no referential integrity, duplicate names, hard to query).

## Decision 6: Collection Scheduling

**Choice**: Optional `starts_at`/`ends_at` on collections. Collection visibility in public API (Spec 004) will filter based on these timestamps.

**Alternatives**: Boolean `is_active` only (less flexible for scheduled collections).
