# Implementation Plan: guest order access and tracking

**Status**: Partially implemented and integrated with guest/account order pages (reviewed 2026-10-25).

## Implemented

- Checkout issues a scoped, expiring, revocable order credential. Private reads and guest-order claims require both an exact-order match and `order.read`; review submission separately requires `review.create`.
- The private order view exposes accepted item/payment/fulfillment state and a chronological allow-listed lifecycle timeline. It excludes event metadata, internal notes, staff identity, and unknown event types.
- Signed-in customers see the same buyer-safe lifecycle events for orders linked to their account; explicit guest-order claims still require the order credential.
- Private confirmation routes are excluded from indexing. Review submission and claim actions reuse the order-only credential through the same-origin customer BFF.
- Checkout, customer-auth, and review integration tests verify that read, claim, and review operations each enforce their own credential scope; unit and frontend tests cover timeline redaction and rendering.

## Remaining

- Provider-authenticated courier milestones, deduplication, out-of-order event handling, tracking references, and failed-delivery/RTO exception workflows.
- Pickup readiness and collection events after approved location/hours and payment terms exist.
- Customer-visible shipment progress tied to trusted courier events. Current timeline reflects recorded order lifecycle events only.
