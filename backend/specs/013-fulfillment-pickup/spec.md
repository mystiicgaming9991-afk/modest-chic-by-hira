# Feature Specification: Fulfillment and Pickup

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§8.4, 9.2; `BACKEND_TRD.md` §4.9; `BACKEND_LLD.md` §§2.2, 4.3; STORY-010.

## User Scenarios & Testing

### User Story 1 - Pack and Book Delivery (Priority: P1)

Warehouse staff can pack confirmed, financially eligible items and request a courier booking without risking duplicate shipments after a timeout.

**Independent Test**: Pack a confirmed delivery, request booking, simulate a timeout and retry, and verify one courier booking and one shipment allocation.

**Acceptance Scenarios**:

1. **Given** a confirmed order with valid stock and paid online or confirmed COD gate, **When** staff pack it, **Then** packed quantities never exceed ordered unfulfilled quantities.
2. **Given** a booking request, **When** the courier times out, **Then** the request remains visible and retry checks the existing reference before another booking.
3. **Given** a valid booked shipment, **When** handoff is recorded, **Then** only its allocated reserved stock is consumed once.

### User Story 2 - Complete Pickup (Priority: P1)

Staff can prepare a pickup, tell the buyer it is ready, and record verified collection under approved location, time, and payment rules.

**Independent Test**: Prepare and mark a pickup ready, then collect it after the required payment gate; verify one stock consumption and collection record.

**Acceptance Scenarios**:

1. **Given** an eligible pickup, **When** staff mark it ready, **Then** the pickup shows location and readiness without consuming stock.
2. **Given** a ready pickup and satisfied payment terms, **When** collection is recorded, **Then** stock is consumed once and the order reflects fulfillment.

### Edge Cases

- A COD order without confirmation or an online order without verified payment cannot be booked or handed over.
- Two parcels cannot allocate more than an item's unfulfilled quantity.
- An ambiguous courier timeout becomes a visible exception; staff do not blindly create a second booking.
- Pickup cannot be collected twice or from the wrong location.
- Private shipping labels are never exposed through a public tracking view.

## Requirements

### Functional Requirements

- **FR-001**: Packing and shipment allocation MUST be limited to confirmed, fulfillment-eligible orders and remaining item quantities.
- **FR-002**: A delivery booking request MUST retain one stable merchant reference and survive retries without creating duplicate courier orders.
- **FR-003**: Courier lookup, booking result, tracking number, label reference, and unresolved failures MUST be visible to authorized staff.
- **FR-004**: Handoff MUST be recorded with actor/time and consume only allocated reserved quantities exactly once.
- **FR-005**: Pickup MUST have an approved location and explicit preparing, ready, collected, or cancelled progression.
- **FR-006**: Pickup collection MUST enforce the approved payment policy and consume its reservation once; marking ready alone MUST not consume stock.
- **FR-007**: Courier provider selection and pickup operating terms MUST remain disabled until business approval.

### Key Entities

- **Shipment and parcel allocation**: Order-linked delivery request, items, merchant reference, courier outcome, and label.
- **Pickup**: Order, location, readiness, collection, and cancellation record.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Retrying booking after a timeout creates no more than one courier booking for the same shipment reference.
- **SC-002**: 100% of handoff and pickup-collection retries consume stock no more than once.
- **SC-003**: No unconfirmed COD or unverified online order reaches courier handoff.

## Assumptions

- The business approves courier coverage, origin, charges, label access, pickup locations/hours, payment terms, and expiry before launch.
- Courier status updates and customer tracking are governed by the guest order access and tracking feature.
