# Feature Specification: Guest Order Access and Tracking

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.5, 8.8; `BACKEND_TRD.md` §§4.7, 4.9, 13; `BACKEND_LLD.md` §§1.4, 4.3; STORY-011.

## User Scenarios & Testing

### User Story 1 - View My Order Privately (Priority: P1)

A guest with an order-specific credential can see the accepted purchase, payment and fulfillment progress, and customer-safe event history without a customer account.

**Independent Test**: Create two orders, use the first order's credential for both numbers, and verify only the first is readable.

**Acceptance Scenarios**:

1. **Given** a valid credential for an order, **When** the guest opens that order, **Then** they see only its accepted details and safe status history.
2. **Given** a valid credential for another order or no credential, **When** the guest requests an order number, **Then** no private order data is disclosed.

### User Story 2 - Follow Delivery or Pickup Progress (Priority: P1)

A guest can see verified shipment milestones or pickup readiness, while staff can investigate courier exceptions and return-to-origin outcomes.

**Independent Test**: Apply a verified courier milestone, replay it, then apply an out-of-order older milestone; verify one safe current status and complete event history.

**Acceptance Scenarios**:

1. **Given** a trusted courier status, **When** it is received, **Then** tracking history and current shipment state reflect it once.
2. **Given** an unknown, duplicate, or inconsistent status, **When** it arrives, **Then** it is retained for investigation without incorrectly completing the order.

### Edge Cases

- Raw order tokens never appear in query strings, logs, or another order's response.
- Expired or revoked credentials cannot read an order, create a return, or submit a review.
- Public tracking omits internal notes, provider payloads, bank details, and private labels.
- Courier callbacks with invalid authentication do not change shipment or order state.
- RTO is distinct from customer delivery and from COD cash collection.

## Requirements

### Functional Requirements

- **FR-001**: A guest order credential MUST authorize only its exact order and explicit read, return-create, or review-create actions.
- **FR-002**: Guest order detail MUST show accepted item, total, payment, fulfillment, and customer-safe event information without staff-only fields.
- **FR-003**: Expiry or revocation MUST stop all scoped actions immediately.
- **FR-004**: Courier updates MUST be authenticated, deduplicated, mapped to a known shipment, and applied without moving state backward.
- **FR-005**: Delivery exception, failed delivery, and return-to-origin milestones MUST be visible to staff and summarized safely to the buyer.
- **FR-006**: Pickup progress MUST reflect ready and collected events only after the corresponding fulfillment action.
- **FR-007**: Customer access MUST not be recoverable by guessing an order number or another shopper's identity.
- **FR-008**: A later customer account MUST NOT gain a guest order merely from matching email or phone; account claims require the order-specific proof defined in feature 024.

### Key Entities

- **Order access grant**: Exact-order, scoped, expiring private credential.
- **Tracking event**: Trusted normalized shipment or pickup milestone and its source.
- **Delivery exception**: Undelivered, disputed, or return-to-origin event requiring staff action.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cross-order, expired, or revoked credentials reveal zero private order records.
- **SC-002**: Replayed courier events produce one visible milestone and no duplicate order transition.
- **SC-003**: 100% of delivery and RTO outcomes remain distinguishable from payment collection in customer and staff views.

## Assumptions

- Checkout issues the order-specific access credential; fulfillment owns shipment and pickup creation.
- Exact courier event names and coverage are mapped only after an approved provider is selected.
