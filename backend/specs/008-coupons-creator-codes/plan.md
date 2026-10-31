# Implementation Plan: coupons creator codes

**Status**: Partially implemented and connected to storefront checkout (reviewed 2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Unit + contract tests in `tests/`.

## Summary

Coupon administration now supports listing, creating, editing, pausing, catalog scopes, time windows, and redemption limits through permission-gated staff APIs and a frontend screen. Scoped eligibility, integer discounts, quote display, accepted-order reservation, and COD redemption resolution are implemented. A real PostgreSQL checkout journey verifies quote-to-order discount accuracy, payment amount, exact retry replay, and redemption reservation. Staff with `analytics.read` can report accepted order counts, order values, customer discount totals, and current states grouped by the accepted attribution source, campaign, creator code, and order source. The report uses UTC placement dates, retains cancelled orders as historical intake, and labels values as order intake rather than collected or settled revenue. Commission/ROI measures and final attribution rules remain open for business approval.
All models inherit `BaseModel` with full audit columns. API routes follow the shared error contract from Spec 001.
