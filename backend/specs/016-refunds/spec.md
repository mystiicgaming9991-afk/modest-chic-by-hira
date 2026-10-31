# Feature Specification: Refunds

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.6, 8.7; `BACKEND_TRD.md` §4.8; `BACKEND_LLD.md` §2.4; STORY-014.

## User Scenarios & Testing

### User Story 1 - Request and Approve a Refund (Priority: P1)

Authorized staff can request a refund against collected money, and a separately authorized approver can confirm the amount and reason.

**Independent Test**: Request two partial refunds that fit within one payment, reject a third that exceeds collected funds, and verify the approval history.

**Acceptance Scenarios**:

1. **Given** a collected payment, **When** staff request an eligible amount, **Then** a pending refund is recorded without changing the payment to refunded.
2. **Given** a requested amount plus existing pending or completed refunds above collected funds, **When** another request is made, **Then** it is rejected without changing refund balances.
3. **Given** staff lacking approval permission, **When** they attempt approval, **Then** the refund remains pending.

### User Story 2 - Execute and Reconcile a Refund (Priority: P1)

Approved online refunds can be sent safely to the provider; COD or manual refunds require transfer evidence before completion.

**Independent Test**: Retry one approved online refund after a timeout and verify one provider refund; then record evidence for a manual refund and verify its separate completion path.

**Acceptance Scenarios**:

1. **Given** an approved online refund, **When** execution succeeds or is retried, **Then** one provider refund and one completed record exist.
2. **Given** a manual refund without transfer evidence, **When** staff mark it completed, **Then** completion is denied.

### Edge Cases

- Two simultaneous refund requests cannot together exceed the collected payment.
- A provider timeout or unknown outcome stays visible for status lookup and safe retry.
- A payment belonging to another order cannot fund the requested refund.
- Order, payment, and return states remain independently meaningful during a partial refund.

## Requirements

### Functional Requirements

- **FR-001**: Refund creation MUST verify the payment belongs to the order, was collected, and has enough unrefunded balance including pending/processing requests.
- **FR-002**: Refund request and approval MUST be separate authorized actions with actor, time, amount, currency, reason, and audit history.
- **FR-003**: Online execution MUST reuse one stable request identity and reconcile ambiguous provider outcomes before another attempt.
- **FR-004**: COD/manual refund completion MUST require a private bank or transfer evidence reference.
- **FR-005**: Failed or disputed refunds MUST remain in an actionable staff queue without counting as completed cash movement.
- **FR-006**: Partial and full refunds MUST update payment and order reporting without mislabeling the order as cancelled or delivered.

### Key Entities

- **Refund**: Order/payment-linked amount, reason, approval, execution, and evidence state.
- **Refund attempt**: Stable provider request and recoverable outcome.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Under concurrent requests, total pending, processing, and completed refund amounts never exceed collected payment.
- **SC-002**: Retrying an online refund produces no more than one provider refund for its approved request.
- **SC-003**: 100% of manual refunds marked complete retain required evidence and approver history.

## Assumptions

- The business approves refund authority, customer communication, fees, and manual transfer process before launch.
- Return approval does not itself imply money has been refunded; settlement reconciliation is a separate feature.
