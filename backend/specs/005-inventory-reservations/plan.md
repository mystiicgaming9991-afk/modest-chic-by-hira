# Implementation Plan: Inventory and Reservations

**Branch**: `005-inventory-reservations` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Deliver inventory tracking and order reservations: locations, variant-level balances with optimistic concurrency, immutable movement ledger with idempotency, and reservation lifecycle (reserve → consume/release/expire). Concurrent reservations use row-level locks to prevent overselling.

## Technical Context

**Storage**: PostgreSQL 16 — new tables: `inventory_locations`, `inventory_balances`, `inventory_reservations`, `inventory_movements`. Enums: `reservation_status`, `movement_reason`.

**Concurrency**: `SELECT ... FOR UPDATE` on balance rows during reserve/release/consume. Version column on balances for optimistic concurrency on adjustments.

**Testing**: pytest + pytest-asyncio; PostgreSQL required for concurrency tests.

## Design

### Enums
- `reservation_status`: `ACTIVE`, `CONSUMED`, `RELEASED`, `EXPIRED`
- `movement_reason`: `RECEIVE`, `ADJUST`, `RESERVE`, `RELEASE`, `CONSUME`, `EXPIRE`, `RESTOCK`

### Core operations
- `receive_stock(variant_id, location_id, quantity, reason, actor_id)` → increments on_hand, creates movement, idempotent by key
- `adjust_stock(variant_id, location_id, delta, reason, actor_id)` → modifies on_hand, version-checked, creates movement
- `reserve(balance_id, order_item_id, quantity, expires_at)` → increments reserved under row lock, creates reservation + movement, fails if available < quantity
- `release(reservation_id)` → idempotent, decrements reserved, marks RELEASED
- `consume(reservation_id)` → idempotent, decrements both on_hand and reserved, marks CONSUMED
- `expire_stale()` → finds ACTIVE past expires_at, releases them

### Seed
- One default location `main` / "Main Warehouse"

## Integration Status (2026-10-25)

- Warehouse staff can list active locations and variants, inspect balances with on-hand/reserved/available quantities, and page through recent stock movements.
- The staff frontend at `/admin/inventory` is linked from the permission-aware staff home. Receive and adjustment actions use the existing staff permissions and send idempotency keys through the same-origin BFF.
- Adjustments require a staff note, use only the `ADJUST` movement reason, and cannot reduce on-hand below active reservations. Changed-payload retries using the same key are rejected.
- Confirmed/processing orders and pending COD orders without sufficient active, unexpired reservations now appear in a permission-gated staff exception count/list. COD confirmation itself rejects insufficient or expired reservations. Automated handling of late successful provider payments, provider-specific callbacks, reservation-window policy for all payment states, and inspected returns/restock integration remain open under the broader checkout/payment/returns flows.
