# Feature Specification: Guest Checkout

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.4, 8.1; `BACKEND_TRD.md` §§7.1–7.4; `BACKEND_LLD.md` §§1.3, 8.1, 9.2; STORY-006.

## User Scenarios & Testing

### User Story 1 - Review an Accurate Quote (Priority: P1)

A guest can review current items, discounts, delivery or approved pickup charges, and payment choices before placing an order.

**Independent Test**: Quote a mixed cart with an eligible coupon, change one item price, and verify the next quote reflects the current terms.

**Acceptance Scenarios**:

1. **Given** a valid guest cart and serviceable destination, **When** the shopper requests a quote, **Then** the displayed PKR subtotal, discount, shipping, and total are internally consistent.
2. **Given** an unserviceable destination or unapproved commercial option, **When** quoted, **Then** the option cannot be submitted as an accepted order.

### User Story 2 - Place an Order Once (Priority: P1)

A guest supplies contact, fulfillment, payment, and policy acceptance details and receives one order with a private order-access credential, even after a retry.

**Independent Test**: Submit an order, repeat the exact request with the same idempotency identity, and verify the same order and access credential; change the body and verify a conflict.

**Acceptance Scenarios**:

1. **Given** current price, stock, policy, and cart version, **When** the guest submits, **Then** one order, its item snapshots, stock reservations, coupon reservation, payment attempt, and event are accepted together.
2. **Given** an exact retry, **When** the guest resubmits, **Then** the original order and access credential are returned without another stock or coupon use.
3. **Given** a stale cart version or changed total, **When** the guest submits, **Then** the order is not accepted and the guest is prompted to review changes.

### Edge Cases

- Two guests racing for the last unit cannot both place accepted orders.
- A duplicate idempotency identity with different request content returns a conflict.
- A crash after accepting an order but before responding must be recoverable through the same request identity.
- Failed payment-session creation cannot confirm an online order or hide the accepted pending order.
- Each line discount allocation is exact and totals with shipping equal the accepted order total.

## Requirements

### Functional Requirements

- **FR-001**: The quote MUST use current product, stock, coupon, shipping, and policy terms and clearly identify serviceability and available payment methods.
- **FR-002**: Checkout MUST require a valid guest identity, anti-forgery proof, current cart version, valid customer contact, approved policy acceptance, and a unique request identity.
- **FR-003**: Acceptance MUST revalidate current price, coupon, serviceability, and stock before recording the order; an earlier quote alone is never authoritative.
- **FR-004**: Order, snapshots, reservation, coupon use, payment attempt, access credential, event, and cart clear MUST succeed or fail as one business transition.
- **FR-005**: An identical retry MUST return the original order and exact access credential until credential expiry; a changed retry MUST fail with a conflict.
- **FR-006**: COD orders MUST start pending confirmation; online orders MUST start pending payment; pickup pay-on-collection is available only after approved terms and starts under its documented gate.
- **FR-007**: Monetary totals MUST use integer PKR minor units and exactly reconcile line totals, discounts, shipping, and order total.
- **FR-008**: Checkout MUST not expose another guest's order or credential through a guessed identifier or failed retry.
- **FR-009**: This guest flow MUST remain usable without a customer account after feature 024 adds optional passwordless email login.

### Key Entities

- **Checkout request identity**: Canonical accepted request and retry identity.
- **Order access credential**: Private, scoped capability for one accepted order and exact retry replay.
- **Accepted quote and snapshots**: Current commercial calculation frozen on order acceptance.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Under concurrent last-unit checkout, accepted reservations never exceed available stock.
- **SC-002**: 100% of exact retries return the same order and access credential; 100% of changed retries are rejected.
- **SC-003**: Every accepted order has reconciled line, discount, shipping, and total values with no fractional minor units.
- **SC-004**: A guest can complete a valid checkout in under three minutes, excluding external payment time.

## Assumptions

- Shipping charges and pickup payment terms require business approval; unapproved options remain unavailable.
- Payment verification and later fulfillment are separate features; checkout records intent, not a provider-confirmed result.
