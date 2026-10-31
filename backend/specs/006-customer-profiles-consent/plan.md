# Implementation Plan: customer profiles consent

**Status**: Partially implemented and verified locally (2026-10-25).
**Database tables**: See migration files in `migrations/versions/`.
**Code**: `src/modest_chic_backend/modules/` and `api/v1/`.
**Tests**: Customer profile unit tests and PostgreSQL checkout/concurrency tests in `tests/`.

## Summary

Guest checkout resolves an unambiguous normalized phone and name identity to a
profile under a PostgreSQL transaction lock, and attaches the profile to the
accepted order without changing order contact/address snapshots. Conflicting
names on a shared phone create separate profiles. Staff with `customer.read`
can search profiles and inspect linked order state/event history; profile
address and consent changes require the separate `customer.manage` permission
and record the staff actor. The staff workspace reads saved addresses for
`customer.read` users and lets `customer.manage` users add or version-edit addresses.
Address responses preserve recipient/contact and delivery-note fields; customer
and address row locks serialize updates, stale versions conflict, and default-address
replacement clears the former default. Existing order snapshots are not edited. The
staff workspace also displays the latest marketing email decision
as read-only; consent recording and sending remain gated by approved language
and evidence/suppression policy.

The account page now lets a signed-in customer inspect whether optional
marketing email consent is active and withdraw an existing decision. Withdrawal
appends one `customer_self_service` decision under a customer-row lock, carries
forward the recorded policy version, and is safe to repeat. Customer opt-in,
current-consent enforcement for messages/exports, approved privacy copy, and
return-to-origin history remain open. The business has not approved retention
policy or marketing consent language, so export and marketing delivery stay
disabled.
