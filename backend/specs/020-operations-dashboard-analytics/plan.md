# Implementation Plan: operations dashboard analytics

**Status**: Partially implemented and connected to staff screens (reviewed 2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Unit + contract tests in `tests/`.

## Summary

The permission-gated home snapshot reports current order-state counts plus actionable COD confirmation, reservation exceptions, packing, review moderation, zero-available inventory, and configured low-stock queues. Reservation exception counts and order results share one filter covering pending COD and fulfillment-eligible orders with missing or expired active reservations. Low-stock thresholds are optional per SKU/location, have no inferred default, and are manageable by owner/warehouse staff with a dedicated permission. Queue counts and paginated results share the same filter; threshold edits are audited. Queue cards link to their exact filtered staff lists and counts appear only with the corresponding permission. An attribution report groups accepted order snapshots by source, campaign, creator code, and order source, with separate discount totals and current-state counts. It uses UTC order-placement dates and does not equate COD order value with cash collected. Booking, delivery/payment exceptions beyond stock reservation coverage, returns/refunds, settlements, reconciled financial reporting, funnel events, deployment/recovery evidence, and final KPI acceptance checks remain open. All models inherit `BaseModel` with full audit columns. API routes follow the shared error contract from Spec 001.
