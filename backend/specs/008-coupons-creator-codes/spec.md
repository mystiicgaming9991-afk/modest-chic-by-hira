# Feature Specification: Coupons and Creator Codes

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.6, 8.1, 8.7; `BACKEND_TRD.md` §4.11; `PRD.md` §11; STORY-016.

## User Scenarios & Testing

### User Story 1 - Configure a Promotion (Priority: P1)

Authorized staff can define a dated coupon or creator code with eligible products/categories, value, minimum spend, and use limits.

**Independent Test**: Create a scoped code, apply it to eligible and ineligible carts, and verify the correct customer-facing discount.

**Acceptance Scenarios**:

1. **Given** a valid active code and eligible cart, **When** it is quoted, **Then** the discount respects scope, value, cap, and minimum spend.
2. **Given** an expired, inactive, or ineligible code, **When** it is quoted, **Then** no redemption is created and the shopper sees a non-sensitive reason.

### User Story 2 - Count Use Once (Priority: P1)

The business can limit campaign use without duplicate or oversubscribed redemptions when buyers check out concurrently or retry.

**Independent Test**: Race two eligible checkouts for a one-use code; at most one reserves it, and cancellation releases only that order's reservation.

**Acceptance Scenarios**:

1. **Given** one remaining redemption, **When** two buyers submit simultaneously, **Then** at most one receives the discount.
2. **Given** a reserved redemption, **When** its order is confirmed, **Then** the redemption is consumed once; cancellation or expiry releases it once.

### Edge Cases

- A fixed discount never exceeds eligible subtotal or makes an order total negative.
- A percentage code accepts only a valid rate and respects any maximum discount.
- A customer with multiple contact spellings cannot bypass a per-customer limit.
- A retry with the same checkout identity does not consume another use.

## Requirements

### Functional Requirements

- **FR-001**: Staff with promotion permission MUST be able to create and change code eligibility, validity period, value, and global/per-customer limits.
- **FR-002**: Coupon validation MUST use the current cart and catalog terms and MUST re-evaluate eligibility when an order is accepted.
- **FR-003**: Reserved and consumed uses MUST both count against limits until release or expiry is completed.
- **FR-004**: Coupon redemption MUST have distinct reserved, consumed, released, and expired states with one terminal resolution per order.
- **FR-005**: Concurrent checkout and retry MUST not oversubscribe a use limit or create duplicate redemption for one order.
- **FR-006**: Discount arithmetic MUST use PKR integer minor units and MUST allocate the exact total across eligible order lines.
- **FR-007**: Creator-code attribution MUST be reportable separately from a customer price discount when the campaign defines that distinction.

### Key Entities

- **Coupon or creator code**: Validity, value, eligibility scope, and limits.
- **Redemption**: One order/customer use with reserved-to-final lifecycle and exact discount.
- **Campaign attribution**: Source or creator label attached to an accepted order.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A one-use code yields no more than one active or consumed redemption under 100 simultaneous eligible attempts.
- **SC-002**: 100% of accepted discounts match the displayed eligible rule and are reflected exactly in order-line totals.
- **SC-003**: Retry, cancellation, and expiry never increase the counted uses beyond one per accepted order.

## Assumptions

- Marketing approves campaign scope and terms before activation.
- Checkout owns the accepted price and order; this feature owns coupon eligibility and redemption lifecycle.
