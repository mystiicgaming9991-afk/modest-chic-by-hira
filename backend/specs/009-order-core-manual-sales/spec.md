# Feature Specification: Order Core and Manual Sales

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§6.3, 7.6, 8.1–8.2; `BACKEND_TRD.md` §§4.7, 5, 7; `BACKEND_LLD.md` §§4.1, 5.2; STORY-007.

## User Scenarios & Testing

### User Story 1 - Inspect and Act on Orders (Priority: P1)

Authorized staff can find orders from the storefront or social channels, inspect immutable purchase terms and event history, and perform only valid lifecycle commands.

**Independent Test**: Create an order, search by state and number, perform an allowed transition, and verify its snapshot, actor, and ordered events.

**Acceptance Scenarios**:

1. **Given** an existing order, **When** authorized staff open it, **Then** they see its accepted items, contact/address, totals, payment/fulfillment status, and event history.
2. **Given** an invalid or unauthorized command, **When** staff submit it, **Then** state and history remain unchanged.

### User Story 2 - Capture a Manual Social Order (Priority: P1)

Staff can record a customer order received through Instagram or another approved sales channel with the same stock, pricing, policy, and payment controls as a website order.

**Independent Test**: Create a manual order for an in-stock SKU, verify its social source and accepted snapshots, then retry the request without a duplicate order.

**Acceptance Scenarios**:

1. **Given** valid customer, item, and fulfillment details, **When** authorized staff create a manual order, **Then** one order with explicit source and attribution is recorded.
2. **Given** insufficient stock or an unapproved fulfillment/payment option, **When** staff submit the order, **Then** no order, reservation, or payment attempt is accepted.

### Edge Cases

- Canceling after courier handoff or pickup collection is rejected or routed to a return/refund process.
- Two concurrent commands cannot both apply from the same prior state.
- An item removed from the catalog remains readable through its order snapshot.
- Customer-visible notes are separated from internal staff notes.

## Requirements

### Functional Requirements

- **FR-001**: Every accepted order MUST have a unique human-readable number, explicit source, customer, current state, payment state, fulfillment choice, currency, and accepted total.
- **FR-002**: Each order item MUST retain SKU, title, variant, quantity, unit price, discount, and line total as immutable acceptance snapshots.
- **FR-003**: Accepted contact, address, and policy version MUST remain available after later customer, catalog, or policy changes.
- **FR-004**: Order lifecycle commands MUST enforce documented state transitions, actor permission, preconditions, and an append-only event history.
- **FR-005**: Manual order creation MUST validate current sellable stock, price, customer, and approved fulfillment/payment choices before acceptance.
- **FR-006**: Repeating the same accepted manual-order request MUST return the same business result; a conflicting retry MUST be rejected.
- **FR-007**: Staff search and detail MUST support order number, state, date, source, and customer context without exposing unauthorized personal data.
- **FR-008**: Payment, shipment, return, and refund states MUST remain separately identifiable; no single order-state change may imply an unverified external outcome.
- **FR-009**: Accepted order and item snapshots, source/approved attribution, and append-only, deduplicated lifecycle events MUST retain stable IDs and UTC timestamps sufficient to reconstruct order intake and state-at-time reporting after catalog, customer, or policy changes.

### Key Entities

- **Order and item**: Accepted commercial terms and independent lifecycle state.
- **Order event and note**: Append-only action history and access-controlled commentary.
- **Manual sale source**: Explicit channel and attribution separate from website checkout.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of accepted orders can be reconstructed from their stored snapshots even if the catalog changes.
- **SC-002**: Replaying the same manual order creates exactly one order, reservation set, and payment attempt.
- **SC-003**: 100% of rejected lifecycle commands leave order and event history unchanged.
- **SC-004**: Order intake by day, source, and SKU reconciles to accepted order/item records; replayed commands, later catalog edits, and customer merges do not change historical accepted values.

## Assumptions

- Customer, catalog, inventory, policy, promotion, and payment features provide their own validated rules.
- Website checkout has its own acceptance feature; this feature owns the shared order model and staff manual-order path.
