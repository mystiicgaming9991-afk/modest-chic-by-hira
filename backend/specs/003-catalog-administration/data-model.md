# Data Model: Catalog Administration

All tables inherit `BaseModel` (id, created_at/by, updated_at/by, deleted_at/by). Prices are PKR integer minor units. `product_status` is a PostgreSQL native enum: `DRAFT`, `PUBLISHED`, `ARCHIVED`.

## Enums

```sql
CREATE TYPE product_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED');
```

## Tables

### products

| Field | Type | Notes |
|---|---|---|
| slug | VARCHAR(255) UNIQUE | URL-safe identifier |
| title | VARCHAR(500) | Required |
| description | TEXT | Rich product description |
| fabric | VARCHAR(255) | Material composition |
| care | TEXT | Care instructions |
| dimensions | VARCHAR(255) | Size/fit notes |
| status | product_status | DRAFT → PUBLISHED → ARCHIVED |

Indexes: `idx_product_status`, `idx_product_slug`

### product_variants

| Field | Type | Notes |
|---|---|---|
| product_id | UUID FK → products | ON DELETE RESTRICT |
| sku | VARCHAR(100) UNIQUE | Stock keeping unit |
| color_name | VARCHAR(255) | Required |
| color_hex | CHAR(7) | `#D4C5B9` |
| dimensions | VARCHAR(255) | Variant-specific if different |
| weight_grams | INT | |
| price_minor | INT CHECK ≥ 0 | Regular price in PKR paisa |
| sale_price_minor | INT CHECK ≥ 0, ≤ price_minor | Sale price (nullable) |
| currency | CHAR(3) DEFAULT 'PKR' | |
| is_active | BOOLEAN DEFAULT TRUE | |

Constraints: `uq_variant_sku` UNIQUE; `chk_sale_price` (sale ≤ regular)

### categories

| Field | Type | Notes |
|---|---|---|
| slug | VARCHAR(255) UNIQUE | |
| name | VARCHAR(255) | |
| description | TEXT | |
| parent_id | UUID FK → categories (self) | Hierarchy |
| sort_order | INT DEFAULT 0 | |
| status | product_status | DRAFT → PUBLISHED → ARCHIVED |

### product_categories

| Field | Type | Notes |
|---|---|---|
| product_id | UUID FK → products | ON DELETE CASCADE |
| category_id | UUID FK → categories | ON DELETE CASCADE |
| sort_order | INT DEFAULT 0 | |

PK: (product_id, category_id)

### collections

| Field | Type | Notes |
|---|---|---|
| slug | VARCHAR(255) UNIQUE | |
| name | VARCHAR(255) | |
| description | TEXT | |
| status | product_status | |
| starts_at | TIMESTAMPTZ | Optional scheduled start |
| ends_at | TIMESTAMPTZ | Optional scheduled end |

### collection_products

| Field | Type | Notes |
|---|---|---|
| collection_id | UUID FK → collections | ON DELETE CASCADE |
| product_id | UUID FK → products | ON DELETE CASCADE |
| sort_order | INT DEFAULT 0 | |

PK: (collection_id, product_id)

### product_tags

| Field | Type | Notes |
|---|---|---|
| name | VARCHAR(100) UNIQUE | |

### product_tag_links

| Field | Type | Notes |
|---|---|---|
| product_id | UUID FK → products | ON DELETE CASCADE |
| tag_id | UUID FK → product_tags | ON DELETE CASCADE |

PK: (product_id, tag_id)

### product_media

| Field | Type | Notes |
|---|---|---|
| product_id | UUID FK → products | ON DELETE CASCADE |
| variant_id | UUID FK → variants | ON DELETE SET NULL |
| object_key | VARCHAR(500) | S3 key |
| media_type | VARCHAR(50) | MIME type |
| alt_text | VARCHAR(500) | |
| width | INT | |
| height | INT | |
| sort_order | INT DEFAULT 0 | |
| is_primary | BOOLEAN DEFAULT FALSE | |
| status | product_status | |

## Invariants

- Slug and SKU uniqueness enforced at DB level
- Price changes on variants do not affect existing order snapshots (orders capture price at acceptance time)
- `ON DELETE RESTRICT` on product_id in variants prevents deleting products with active variants — archive instead
- All catalog mutations record audit with actor_id and entity type/id
- Public queries (future Spec 004) filter by `status = 'PUBLISHED'` and `is_active = TRUE`
