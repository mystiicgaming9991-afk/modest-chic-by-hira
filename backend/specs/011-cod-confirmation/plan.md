# Implementation Plan: cod confirmation

**Status**: Partially implemented and connected to the staff COD queue (reviewed 2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Unit + contract tests in `tests/`.

## Summary

The staff queue supports contact attempt history, confirmation with a valid reservation, and decline with one-time stock and coupon release. Pending COD orders whose stock reservation is missing, insufficient, or expired are marked in the queue, and confirmation is disabled while the exception persists. Contact attempts use an idempotency key so retrying the same request does not duplicate history. Eligible cancellation is available through the order detail workflow. The approved confirmation timeout and setting-controlled follow-up window remain unimplemented until the business supplies those terms. All models inherit `BaseModel` with full audit columns. API routes follow the shared error contract from Spec 001.
