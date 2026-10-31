# Feature Specification: Returns and Exchanges

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.5–7.6, 8.5; `BACKEND_TRD.md` §4.10; `BACKEND_LLD.md` §§2.5, 4.4; STORY-013.

## User Scenarios & Testing

### User Story 1 - Request an Item-Level Return (Priority: P1)

A guest can request a return or exchange for eligible purchased items through their order-specific access, and staff can approve or reject with a reason.

**Independent Test**: Submit a request for one purchased unit, reject a request for another order's item, and verify the first request enters staff review.

**Acceptance Scenarios**:

1. **Given** an eligible delivered item and valid order access, **When** a guest requests a quantity within their remaining entitlement, **Then** a pending request is recorded.
2. **Given** an item from another order or quantity above remaining entitlement, **When** requested, **Then** no request is created.

### User Story 2 - Inspect and Resolve Goods (Priority: P1)

Staff record receipt, inspect actual quantities and condition once, then either restock sellable goods, initiate a refund, or arrange an approved exchange.

**Independent Test**: Receive and inspect a two-unit request with one sellable and one damaged unit; verify only the sellable unit restocks and a duplicate inspection changes nothing.

**Acceptance Scenarios**:

1. **Given** an approved request, **When** staff record physical receipt and inspection, **Then** each item has final received quantity, condition, disposition, and actor.
2. **Given** a return resolution, **When** an eligible refund completes, **Then** the return can become resolved.
3. **Given** an exchange without approved price and shipping terms, **When** staff attempt resolution, **Then** no replacement is promised or marked resolved.

### Edge Cases

- Cumulative active and resolved return quantities cannot exceed purchased quantity, even with concurrent requests.
- Inspected received quantity cannot exceed the requested amount; repeated inspection with changed numbers conflicts.
- Damaged or rejected goods never increase sellable stock.
- A replacement order must be linked to the return and reserve its own stock; it cannot silently overwrite the original order.

## Requirements

### Functional Requirements

- **FR-001**: Guest return and exchange requests MUST require the exact order access scope and item ownership, plus the effective approved return policy.
- **FR-002**: Requested quantity across all active and resolved requests MUST not exceed the purchased item quantity.
- **FR-003**: Staff decisions MUST record actor, time, reason, and policy version; rejection MUST not restock or refund.
- **FR-004**: Receipt and inspection MUST record final cumulative received quantity within the requested amount, condition, and disposition once per item.
- **FR-005**: Sellable stock MUST increase only for inspected `RESTOCK` quantities, once per return item; damaged and rejected quantities MUST not increase it.
- **FR-006**: A return MUST not be resolved until its required refund or other approved disposition completes.
- **FR-007**: An exchange MUST remain unresolved until approved price-difference, shipping, and refund terms are applied and a linked replacement order is financially and physically eligible.

### Key Entities

- **Return request and item**: Original order, requested quantity, decision, receipt, inspection, and resolution.
- **Replacement order**: Explicitly linked exchange order with its own stock and financial obligations.

## Success Criteria

### Measurable Outcomes

- **SC-001**: No item can accumulate active/resolved return requests beyond its purchased quantity under concurrency.
- **SC-002**: Duplicate inspection or restock actions increase sellable stock no more than once.
- **SC-003**: 100% of resolved exchanges identify the original return, replacement order, and approved financial terms.

## Assumptions

- The business approves the return window, item-condition rules, fees, shipping payer, and exchange price-difference treatment before enabling relevant paths.
- Refund execution and replacement fulfillment are owned by their separate features.
