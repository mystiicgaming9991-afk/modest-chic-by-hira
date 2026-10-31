# Feature Specification: Inventory and Reservations

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§6.3, 7.6, 8.1, 8.6; `BACKEND_TRD.md` §§4.5, 7; `BACKEND_LLD.md` §§3.2, 5.3; STORY-002.

## User Scenarios & Testing

### User Story 1 - Maintain Trustworthy Stock (Priority: P1)

Warehouse staff can receive, adjust, and inspect variant stock at the correct location while retaining a reasoned movement history.

**Independent Test**: Receive units, record a damaged-unit adjustment, and verify on-hand, reserved, and available quantities and their movement history.

**Acceptance Scenarios**:

1. **Given** a valid SKU and location, **When** staff receive stock, **Then** on-hand increases by the recorded quantity with a traceable movement.
2. **Given** an adjustment that would make a balance invalid, **When** staff submit it, **Then** no balance or movement changes.

### User Story 2 - Protect Orders with Reservations (Priority: P1)

Checkout and manual-order flows can reserve sellable units, release unused units, and consume units once at handoff or pickup collection.

**Independent Test**: Race two orders for one remaining unit; one succeeds and one receives a stock conflict, then release or consume the winning reservation exactly once.

**Acceptance Scenarios**:

1. **Given** one available unit, **When** two buyers attempt to reserve it, **Then** no more than one active reservation is created.
2. **Given** an eligible pending order with an expired reservation, **When** expiry runs, **Then** the reservation releases once and the order is handled according to its payment state.
3. **Given** a paid or confirmed order, **When** a scheduled expiry runs, **Then** its required active stock remains reserved.

### Edge Cases

- Duplicate release, consume, or restock commands do not repeat a movement.
- A late payment after reservation expiry requires a new reservation or an exception; it cannot authorize shipment without stock.
- Negative, zero, or wrong-location adjustments cannot corrupt stock.
- Multiple-SKU operations use a consistent ordering to avoid deadlocks and overselling.

## Requirements

### Functional Requirements

- **FR-001**: Every active variant/location MUST expose nonnegative on-hand, reserved, and available balances, with available equal to on-hand minus reserved.
- **FR-002**: Authorized staff MUST be able to receive and adjust stock with reason, quantity, actor, time, and location recorded in an immutable movement history.
- **FR-003**: Order reservation MUST fail when sellable available stock is insufficient, including under simultaneous orders.
- **FR-004**: Reservation release and consumption MUST be idempotent and MUST preserve balance and order-item quantity limits.
- **FR-005**: Expiry MUST recheck order and payment state before releasing stock; verified paid or confirmed orders MUST retain required stock.
- **FR-006**: A late successful payment with no active reservation MUST re-reserve available stock or create a visible exception before fulfillment.
- **FR-007**: Returned goods MUST enter sellable inventory only after the returns feature records a valid inspected restock decision.

### Key Entities

- **Inventory location and balance**: Variant-level on-hand, reserved, and available quantities at a location.
- **Reservation**: Quantity temporarily committed to one order item and its lifecycle.
- **Movement**: Immutable reasoned stock change with actor and idempotency identity.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Across 100 concurrent attempts for one remaining unit, no more than one unit is reserved.
- **SC-002**: 100% of release, expiry, and consumption retries leave balances unchanged after the first successful transition.
- **SC-003**: Every stock balance change is explainable by a movement and actor or system event.

## Assumptions

- The business supplies opening stock and approves reservation windows; no duration is hard-coded by this spec.
- Checkout, COD, payment, fulfillment, and returns own their order decisions and invoke inventory rules at the documented transitions.
