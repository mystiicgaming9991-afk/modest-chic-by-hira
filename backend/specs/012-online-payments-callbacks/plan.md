# Implementation Plan: online payments and callbacks

**Status**: Not enabled; provider-dependent work remains (reviewed 2026-10-25).
**Current behavior**: Storefront checkout accepts COD only. Orders create payment-attempt records, but no online payment session or provider callback is exposed.

## Implemented

- Payment attempt and event persistence models exist and checkout/manual order creation records the initial attempt.
- Online payment and pickup settings are rejected until their required provider/account or location configuration is approved.
- Financial summaries remain disabled rather than treating order placement as collected revenue.

## Remaining

- Select an approved provider and account, enablement terms, currencies, callback authentication, and refund process.
- Implement durable provider event receipt, account-scoped deduplication, signature and amount/reference validation, monotonic transitions, late-paid stock recovery, and a staff exception queue.
- Add provider contract/integration tests and a staff verification path using the same validation rules.
