# Implementation Plan: returns and exchanges

**Status**: Schema only; return workflow is not implemented (reviewed 2026-10-25).

## Implemented

- Return and return-item persistence models and the initial database migration exist.
- Customer-facing return policy pages exist, but no effective return-window/condition rule is enforced by an API workflow.

## Remaining

- Approve return window, eligible conditions, fees, and shipping responsibility; bind requests to the effective policy version.
- Add exact-order-token return requests, item ownership checks, cumulative quantity locking, and customer-safe request status.
- Add permissioned staff decisions and reason history; receipt and inspection must be idempotent and record condition/disposition.
- Restock only inspected sellable quantities once. Connect resolution to approved refund or exchange terms and linked replacement orders.
- Add API, concurrency, stock, and browser acceptance coverage before enabling returns/exchanges.
