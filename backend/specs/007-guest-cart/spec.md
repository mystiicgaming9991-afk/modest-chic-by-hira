# Feature Specification: Guest Cart

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.3–7.4; `BACKEND_TRD.md` §4.6; `BACKEND_LLD.md` §1.2; STORY-005.

## User Scenarios & Testing

### User Story 1 - Build a Guest Cart (Priority: P1)

A shopper can add, change, remove, and return to selected variants without creating an account.

**Independent Test**: Start a guest cart, add two variants, edit one quantity, remove one, and reload with the same browser identity.

**Acceptance Scenarios**:

1. **Given** a published active variant, **When** a shopper adds it, **Then** the cart shows the requested quantity and current subtotal.
2. **Given** a returning guest with a valid cart, **When** they reopen the shop, **Then** their selected lines and version are restored.

### User Story 2 - Revalidate Before Purchase (Priority: P1)

The cart makes changed price, stock, or publication state visible before checkout rather than promising stale terms.

**Independent Test**: Add a variant, lower its stock or archive it, and verify the cart reports the change and checkout cannot accept the stale line.

**Acceptance Scenarios**:

1. **Given** a cart whose price or availability changed, **When** it is read or changed, **Then** the shopper sees current values and a clear correction prompt.
2. **Given** a stale cart version, **When** checkout begins, **Then** the change is rejected without creating an order.

### Edge Cases

- Missing or invalid guest identity creates no access to someone else's cart.
- Duplicate add requests for the same variant do not create duplicate lines.
- Quantity zero, negative, oversized, or above allowed stock is rejected or normalized according to the documented cart contract.
- An expired cart cannot be restored, but public browsing remains available.

## Requirements

### Functional Requirements

- **FR-001**: A guest MUST be able to create and resume one active cart tied to a protected browser identity.
- **FR-002**: Cart mutations MUST support add, quantity change, and removal of published active variants only.
- **FR-003**: Every successful mutation MUST increment a cart version and return current item count, subtotal, and PKR currency.
- **FR-004**: Cart totals MUST be recalculated from current catalog prices; cart values are advisory and never the accepted order total.
- **FR-005**: Cart read and mutation MUST identify unavailable, archived, or price-changed lines and prevent stale checkout acceptance.
- **FR-006**: Guest cart mutations MUST verify browser anti-forgery and allowed-origin controls before changing state.
- **FR-007**: Only the correct guest identity may access or change a cart; expired carts MUST be removed or made inaccessible under the approved retention rule.

### Key Entities

- **Guest cart**: One browser-bound collection of selected items with version and expiry.
- **Cart line**: Active variant and requested quantity; no authoritative price snapshot.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A returning guest can restore an unexpired cart in one page visit.
- **SC-002**: 100% of cart changes increase the version and return a current subtotal.
- **SC-003**: 100% of invalid or another guest's cart mutations leave the cart unchanged.

## Assumptions

- The existing authentication feature provides safe anti-forgery bootstrapping; guest identity is separate from staff sessions.
- Stock is reserved only by checkout or an authorized manual order, never by adding to cart.
