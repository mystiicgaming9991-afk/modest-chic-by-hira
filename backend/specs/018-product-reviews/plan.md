# Implementation Plan: product reviews

**Status**: Implemented and integrated with the storefront (2026-10-25).
**Database tables**: `reviews`, with rating/status checks, one review per order item, and persisted moderation reason in migration `0018_review_workflow`.
**Code**: `src/modest_chic_backend/modules/reviews/`, `api/v1/reviews.py`, `api/v1/admin_reviews.py`, and the customer review submission route.
**Tests**: PostgreSQL integration coverage in `tests/integration/modules/reviews/test_review_workflow.py`.

## Summary

- Review creation requires a valid, unexpired order token scoped to `review.create`, an order in `FULFILLED` or `COMPLETED`, and a fully fulfilled item from that exact order. A unique database constraint and an order lock prevent duplicate submissions.
- New reviews stay pending. Staff with `review.moderate` must record a reason to approve or reject; the action records its actor, time, and audit event.
- Public product pages read approved reviews only. The count and average use that same approved set, pages use a stable cursor, and public review data omits customer identity and moderation details.
- The order confirmation page submits eligible reviews using the existing HttpOnly order cookie. The product page displays approved feedback and the staff workspace provides the moderation queue.
- The migration checks for existing columns and constraints because earlier schema creation uses live model metadata and may already have applied the review invariants on a fresh database.
