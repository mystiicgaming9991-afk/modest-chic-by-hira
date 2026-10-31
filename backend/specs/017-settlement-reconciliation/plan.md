# Implementation Plan: settlement reconciliation

**Status**: Schema only; reconciliation workflow is not implemented (reviewed 2026-10-25).

## Implemented

- Settlement batch and settlement-line persistence models and initial migration exist.
- Analytics avoids reporting collected or settled revenue from order totals alone.

## Remaining

- Define supported courier/provider statement format and the business-day/currency rules.
- Implement safe import, source-file identity, row-level deduplication, matching to COD/payment/refund events, and unmatched/ambiguous exception handling.
- Add permissioned reconciliation, immutable decisions, totals that reconcile to source lines, and staff drill-down/export controls.
- Add fixture-backed import/replay/mismatch tests and a browser workflow before displaying settlement totals.
