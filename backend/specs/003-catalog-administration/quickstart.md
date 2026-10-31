# Quickstart: Catalog Administration

## Prerequisites

1. PostgreSQL 16 and Redis 7 are running, and the API is configured per the
   [backend quickstart](../001-staff-authentication/quickstart.md).
2. Migrations are at the current head (`0021_order_policy_acceptances` as of
   2026-10-25).
3. An active staff user has `catalog.read` and `catalog.write` permissions.
4. Set `TOKEN`, `CSRF`, and the `cookies.txt` jar using the authenticated
   procedure in [Spec 002](../002-commerce-foundation-policies/quickstart.md).
   `http://localhost:3000` must be in `TRUSTED_ORIGINS`.

Admin mutations require the trusted `Origin` and signed double-submit CSRF
cookie/header even when requests also carry a bearer token. Define this helper
after authenticating:

```bash
admin_write() {
  curl -sS -b cookies.txt -c cookies.txt \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:3000" \
    -H "X-CSRF-Token: $CSRF" "$@"
}
```

## Create, Publish, and Archive a Product

Create a draft product with an active variant. Prices are PKR minor units.

```bash
PRODUCT=$(admin_write -X POST \
  -d '{
    "slug": "lawn-embroidered-kurta",
    "title": "Lawn Embroidered Kurta",
    "description": "Lightweight summer kurta with embroidered neckline.",
    "fabric": "Lawn",
    "care": "Dry clean recommended",
    "dimensions": "Available in S, M, L",
    "variants": [{
      "sku": "LEK-S-RED",
      "color_name": "Crimson Red",
      "color_hex": "#DC143C",
      "price_minor": 350000,
      "sale_price_minor": 320000
    }]
  }' \
  http://localhost:8000/api/v1/admin/catalog/products)
PRODUCT_ID=$(printf '%s' "$PRODUCT" | jq -r '.id')
PRODUCT_UPDATED_AT=$(printf '%s' "$PRODUCT" | jq -r '.updated_at')
```

The create response is a product summary. Read its detail to get the generated
variant ID and version before changing either resource:

```bash
DETAIL=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/admin/catalog/products/$PRODUCT_ID")
VARIANT_ID=$(printf '%s' "$DETAIL" | jq -r '.variants[0].id')
VARIANT_UPDATED_AT=$(printf '%s' "$DETAIL" | jq -r '.variants[0].updated_at')
```

Product and variant edits require the version returned by the previous read.
Archiving uses its dedicated POST action; a generic product PATCH cannot archive.

```bash
admin_write -X PATCH \
  -d "{\"expected_updated_at\":\"$PRODUCT_UPDATED_AT\",\"status\":\"PUBLISHED\"}" \
  "http://localhost:8000/api/v1/admin/catalog/products/$PRODUCT_ID"

admin_write -X PATCH \
  -d "{\"expected_updated_at\":\"$VARIANT_UPDATED_AT\",\"price_minor\":350000,\"sale_price_minor\":280000}" \
  "http://localhost:8000/api/v1/admin/catalog/variants/$VARIANT_ID"

admin_write -X POST \
  "http://localhost:8000/api/v1/admin/catalog/products/$PRODUCT_ID/archive"
```

## Categories, Collections, Tags, and Media

- Create a child category with `POST /api/v1/admin/catalog/categories` and its
  parent UUID. Replace a product's ordered category IDs with
  `PUT /api/v1/admin/catalog/products/{product_id}/categories`; include the
  product's current `expected_updated_at`.
- Replace a product's ordered tag IDs with
  `PUT /api/v1/admin/catalog/products/{product_id}/tags`; include the same
  product version. `POST /api/v1/admin/catalog/tags` creates reusable tags.
- Create a collection with `POST /api/v1/admin/catalog/collections`. Replace
  its ordered product IDs with `PUT
  /api/v1/admin/catalog/collections/{collection_id}/products` and the current
  collection `expected_updated_at`.
- `POST /api/v1/admin/catalog/products/{product_id}/media` attaches metadata
  for an already stored `object_key`; it does not upload a file or configure
  public media delivery. Keep the storefront media workflow disabled until a
  storage provider and delivery URL are configured.

## Validation Checklist

The following checks are specified for the manual smoke run. Do not mark them
complete until the requests have been run against a disposable database.

- [ ] Product creates in DRAFT and is absent from public discovery
- [ ] Duplicate slug and duplicate SKU return validation errors
- [ ] A sale price above its regular price is rejected
- [ ] Product publish and variant price updates succeed with current versions
- [ ] A stale product, variant, category, or collection version is rejected
- [ ] A dedicated archive action hides the product from public discovery
- [ ] Category hierarchy and ordered collection membership persist
- [ ] Media metadata attaches to an existing object key (no file upload)
- [ ] `uv run ruff check src tests` passes
- [ ] `uv run mypy src` passes
