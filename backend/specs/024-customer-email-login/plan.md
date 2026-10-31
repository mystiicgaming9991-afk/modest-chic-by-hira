# Implementation Plan: customer email login

**Status**: Implemented and verified locally (2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Integration coverage in `tests/integration/modules/customers/test_customer_auth.py`; storefront build and lint pass.

## Summary

Email OTP challenges are rate limited, superseded on resend, HMAC protected,
single use, and exhausted after five invalid attempts. Verified addresses map
to a separate unique account record so guest checkout contact emails do not
silently create ownership links. Customer sessions are opaque, expiring,
revocable credentials. Authenticated orders link during checkout; guest orders
require the existing order access credential to claim, with an audit event.

The storefront exposes account sign-in, order history, session actions, and a
confirmation-page claim action through HttpOnly cookie backed API routes. Email
delivery uses the transactional outbox; production delivery still requires
the configured email provider and has not been exercised against a live mail
service.
