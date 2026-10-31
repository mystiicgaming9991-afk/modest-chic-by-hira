# Implementation Plan: refunds

**Status**: Schema only; refund workflow is not implemented (reviewed 2026-10-25).

## Implemented

- Refund persistence model and initial migration exist.
- Financial reporting remains unavailable until refund/payment records can support reconciled values.

## Remaining

- Add permissioned refund request and separate approval, with locks that cap all pending/completed refunds at collected funds.
- Add provider execution with safe retry/status lookup for online refunds and transfer-evidence requirements for COD/manual refunds.
- Record actor, amount, reason, provider/manual reference, transitions, and event history without conflating refund and order state.
- Integrate return resolution and staff UI; add concurrent, replay, authorization, and browser tests.
- Do not enable execution until payment provider and manual transfer evidence policies are approved.
