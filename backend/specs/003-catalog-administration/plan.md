# Implementation Plan: Catalog Administration

**Current integration status (2026-10-25)**: Product, variant, category, collection, tag, and existing-media metadata workflows are connected to the staff frontend. Media attachment records the staff actor, validates variant ownership, and serializes primary-image replacement per product or variant. File upload and public media delivery remain open until storage is configured. Other catalog writes use row locks and `expected_updated_at`; archive has its own permission-gated action; publication requires an active variant. Product-tag assignment and taxonomy membership concurrency are implemented.

**Branch**: `003-catalog-administration` (feature directory) | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-catalog-administration/spec.md`

## Summary

Deliver the catalog backend: products with draft/published/archived lifecycle, sellable variants with unique SKUs and PKR prices, categories with self-referencing hierarchy, ordered collections, product tagging, and product media records. All state transitions are atomic with audit trail. Public visibility is gated by publication status. Build on the existing `BaseModel` audit columns and the `settings.manage`/`catalog.write`/`catalog.archive` permission model.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI; Pydantic v2; SQLAlchemy 2 async; Alembic; asyncpg

**Storage**: PostgreSQL 16 — new tables: `products`, `product_variants`, `categories`, `product_categories`, `collections`, `collection_products`, `product_tags`, `product_tag_links`, `product_media`

**Testing**: pytest, pytest-asyncio, HTTPX ASGI transport, PostgreSQL 16 integration tests; Ruff and mypy

**Target Platform**: Linux container

**Constraints**: All writes within single transaction with audit; `product_status` enum: `DRAFT`, `PUBLISHED`, `ARCHIVED`; unique slug and SKU enforced at DB level; variant prices in PKR integer minor units; media upload validation with type/size constraints

**Scale/Scope**: ~50–200 products, ~200–800 variants, ~5–20 categories, ~5–15 collections

## Constitution Check

| Gate | Result | Evidence |
|---|---|---|
| Contract-first modular design | PASS | New `modules/catalog/` follows existing module pattern; OpenAPI contract precedes routes. |
| Test-first development | PASS | Every behavior task starts with a failing test. |
| Atomic domain changes | PASS | Product/variant/category/media writes commit with audit log in one transaction. |
| Secure defaults | PASS | `catalog.write`/`catalog.archive` permissions gate mutations; slug/SKU uniqueness at DB level. |
| Observable, simple operations | PASS | Structured audit on every catalog change; no new infrastructure. |
| Python/FastAPI/PostgreSQL constraints | PASS | Existing stack; all models inherit `BaseModel` for audit columns. |

## Existing Slice Compatibility

- **BaseModel**: All new models inherit from `BaseModel` (id, created_at/by, updated_at/by, deleted_at/by).
- **Audit**: Catalog mutations produce `AuditLog` records via `AuditRepository`.
- **Permissions**: Uses existing `catalog.write`, `catalog.archive`, `catalog.read` from seed data.
- **Error contract**: Uses existing `ApplicationError` / `{code, message}` envelope.
- **Money**: `price_minor` and `sale_price_minor` stored as INT (PKR paisa); API accepts/produces decimal strings per shared conventions.

## Project Structure

### Documentation

```text
specs/003-catalog-administration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/openapi.yaml
└── tasks.md
```

### Source Code

```text
backend/src/modest_chic_backend/
├── modules/catalog/            # NEW
│   ├── __init__.py
│   ├── models.py               # All 9 catalog entities
│   ├── schemas.py              # Pydantic request/response
│   ├── repository.py           # Read/write with optimistic concurrency
│   ├── service.py              # Business logic + audit
│   └── enums.py                # ProductStatus enum
├── api/v1/
│   └── catalog.py              # NEW: /admin/catalog routes
```

## Data Model Summary

Per `BACKEND_TRD.md` §4.4, adapted to use `BaseModel`:

- **products**: slug (unique), title, description, fabric, care, dimensions, status (DRAFT/PUBLISHED/ARCHIVED)
- **product_variants**: FK product, SKU (unique), color_name/hex, dimensions, weight_grams, price_minor, sale_price_minor, currency(PKR), is_active
- **categories**: slug (unique), name, description, parent_id (self-ref FK), sort_order, status
- **product_categories**: (product_id, category_id) PK, sort_order
- **collections**: slug (unique), name, description, status, starts_at, ends_at
- **collection_products**: (collection_id, product_id) PK, sort_order
- **product_tags**: name (unique)
- **product_tag_links**: (product_id, tag_id) PK
- **product_media**: FK product/variant, object_key (S3 key), media_type, alt_text, width, height, sort_order, is_primary, status

## Migration

`0004_catalog.py` — creates all 9 tables with enums, constraints, and indexes per TRD.
