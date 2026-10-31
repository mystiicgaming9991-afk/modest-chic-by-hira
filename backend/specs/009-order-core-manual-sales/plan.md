# Implementation Plan: order core manual sales

**Status**: Partially implemented and integrated with staff manual-order entry (reviewed 2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Unit + contract tests in `tests/`.

## Summary

The staff manual-order workflow now creates SOCIAL or MANUAL COD orders from current published variants, validates approved fulfillment terms, locks and reserves stock, resolves a customer profile, records catalog and attribution snapshots, and supports exact idempotent replay. It retains links to the effective approved checkout, shipping, and returns policy versions. An authenticated staff form uses the live catalog and configured delivery/pickup cities. The order-manager role gained catalog read access through migration 0014. Staff can search orders by number/customer/state/date/source and inspect accepted snapshots and separate payment/fulfillment/refund records. Starting processing for a confirmed order is row-locked and idempotent, and now rejects missing or expired stock reservations; the order detail page shows the stock exception and disables the action.

Authorized fulfillment staff can now hand off fully packed delivery orders through a replay-safe command that consumes the matching active reservations and marks shipments/order fulfilled together. Staff with `order.cancel` can cancel pending, confirmed, or processing orders before external fulfillment and while payment remains pending or failed; the command records a reason and actor, releases active stock and eligible coupon redemption, and marks unhanded packed shipments or uncollected pickups cancelled. Both commands are available in the staff order detail screen. Payment reversal, courier booking/tracking, pickup collection, and return/refund handling remain owned by their respective gated workflows. All models inherit `BaseModel` with audit columns. API routes follow the shared error contract from Spec 001.
