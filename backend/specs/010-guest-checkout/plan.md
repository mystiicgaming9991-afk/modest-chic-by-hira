# Implementation Plan: guest checkout

**Status**: Implemented and connected to the storefront (reviewed 2026-10-25).

- The storefront requests a current backend quote, displays accepted totals and all effective checkout, shipping, and returns policies, and submits the buyer's COD order through the same-origin commerce BFF.
- Checkout binds acceptance to the quoted cart version and total, the exact checkout, shipping, and returns policy versions, coupon, and stable idempotency key; backend replay returns the original order while changed replay conflicts. The order retains each accepted policy version as an immutable link.
- The browser stores the validated request context in same-tab session storage before submission so a lost response can retry with the same key and recover the private order credential.
- Integration and frontend regression tests cover quote/order flow, exact replay, and interruption recovery. Online payment remains disabled pending provider approval.
