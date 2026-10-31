# Feature Specification: COD Confirmation

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§8.2, 8.6; `BACKEND_LLD.md` §§2.1, 4.1; `PRD.md` §7.1; STORY-008.

## User Scenarios & Testing

### User Story 1 - Confirm a COD Buyer (Priority: P1)

An order manager can work a pending-confirmation queue, record contact attempts, and confirm an order only while its stock reservation is valid.

**Independent Test**: Place a COD order, record a no-answer attempt and then a confirmed attempt, and verify one state transition with complete contact history.

**Acceptance Scenarios**:

1. **Given** a pending COD order with active stock, **When** an authorized manager confirms it, **Then** it becomes confirmed and its reservation remains protected for fulfillment.
2. **Given** a no-answer or follow-up outcome, **When** it is recorded, **Then** the order remains pending and the attempt is visible in sequence.

### User Story 2 - Close Unconfirmed Orders (Priority: P1)

Staff can decline or cancel an order, and a scheduled process can expire a pending order under an approved confirmation window.

**Independent Test**: Cancel a pending order, verify its stock and coupon are released once, then replay cancellation without a second release.

**Acceptance Scenarios**:

1. **Given** a declined pending COD order, **When** the manager closes it, **Then** the order is cancelled with actor, reason, stock release, and coupon release.
2. **Given** a pending order past its approved window, **When** expiry runs, **Then** it is cancelled only if still eligible under current state.

### Edge Cases

- Confirmation after reservation expiry must fail or re-reserve under the approved policy; it cannot silently confirm without stock.
- A late staff confirmation racing expiry cannot both confirm and cancel the order.
- A duplicate contact-attempt request cannot create two audit events or apply a state transition twice.
- Confirmation by staff without order permission changes nothing.

## Requirements

### Functional Requirements

- **FR-001**: Authorized staff MUST have a searchable pending COD queue and full contact-attempt history.
- **FR-002**: Confirmation MUST require a pending COD order, valid active stock, and permission; it MUST preserve the reservation and record actor and time.
- **FR-003**: Decline, cancellation, and approved timeout MUST release stock and reserved coupon use exactly once.
- **FR-004**: No-answer and follow-up outcomes MUST record channel, outcome, notes, actor, and sequence without confirming or cancelling.
- **FR-005**: Competing confirmation and expiry actions MUST yield one valid final state and one corresponding inventory/coupon outcome.
- **FR-006**: The confirmation window and follow-up policy MUST be business settings rather than assumed fixed values.

### Key Entities

- **Confirmation attempt**: Contact channel, result, notes, time, and staff actor.
- **Pending COD order**: Order awaiting an approved customer confirmation decision.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of dispatched COD orders have a recorded confirmation decision.
- **SC-002**: A cancelled pending order releases its reservation and coupon no more than once under retries.
- **SC-003**: Every confirmation decision is traceable to an actor and contact attempt or approved timeout.

## Assumptions

- The business defines who owns follow-up, the confirmation window, and which channels staff may use.
- Delivery booking remains blocked until COD confirmation completes.
