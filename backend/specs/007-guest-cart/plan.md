# Implementation Plan: guest cart

**Status**: Implemented and connected to the storefront (reviewed 2026-10-25).

- The browser uses the commerce BFF for guest cart reads and mutations; the backend remains authoritative for cart identity, version, quantity, and current product/variant state.
- Storefront cart and checkout use the persisted cart rather than browser-only price or stock calculations.
- Cart mutation origin validation, UUID validation, and visible error handling were reviewed and fixed.
- Backend cart/checkout integration tests and frontend cart context tests cover the connected flow.
