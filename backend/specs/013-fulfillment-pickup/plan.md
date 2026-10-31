# Implementation Plan: fulfillment and pickup

**Status**: Partially implemented (2026-10-25).

## Implemented

- Authorized staff can record a delivery shipment allocation after a confirmed order enters processing and passes its payment gate.
- Packing checks remaining ordered quantities and live reservations while locking the order and order items.
- Shipments persist a stable merchant reference, allocation lines, staff actor, and packed event.
- Pack retries with the same key and payload return the existing shipment; reusing a key with a different order or allocation conflicts.
- The staff order detail screen displays shipment references and allocated quantities and exposes the pack action only for eligible delivery orders.

The PostgreSQL checkout integration journey covers pack, exact replay, changed-payload replay rejection, allocation visibility, and over-allocation rejection.

Authorized staff can also record a physical courier handoff after every remaining order unit has been packed. The handoff verifies payment/COD eligibility and exact reservation coverage, consumes stock once with actor attribution, marks each shipment `HANDED_OFF`, and fulfills the order. PostgreSQL integration coverage verifies exact replay and stock/shipment outcomes. Eligible pre-handoff cancellation marks packed shipments cancelled and releases active reservations.

## Not enabled

- Courier lookup/booking, tracking, and labels need an approved provider and operational terms.
- Pickup readiness and collection need an approved location, hours, and payment policy.

These prerequisites are not configured in the application. The staff screen distinguishes packing, physical courier handoff, and provider booking; it never reports a booking that has not been made.
