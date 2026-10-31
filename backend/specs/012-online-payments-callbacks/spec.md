# Feature Specification: Online Payments and Callbacks

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§8.1, 8.3, 9.1; `BACKEND_TRD.md` §§4.8, 4.13, 7; `BACKEND_LLD.md` §§4.2, 6–7; STORY-009, TASK-006.

## User Scenarios & Testing

### User Story 1 - Start a Verified Payment (Priority: P1)

A shopper choosing an approved online method receives a hosted payment path while the order remains pending until a trusted result is verified.

**Independent Test**: Place an online order, open its pending payment attempt, and verify browser return alone does not mark the order paid or dispatchable.

**Acceptance Scenarios**:

1. **Given** an approved payment provider, **When** online checkout is accepted, **Then** the order remains pending payment until verified provider evidence arrives.
2. **Given** a browser success redirect without verified provider evidence, **When** the shopper returns, **Then** the order remains unconfirmed.

### User Story 2 - Process Callbacks Exactly Once (Priority: P1)

The system accepts authenticated provider events, checks merchant, reference, amount, currency, and account, and advances payment and order state without duplicate effect.

**Independent Test**: Send a valid callback twice and a mismatched callback once; verify one paid transition, one recorded duplicate, and one visible exception.

**Acceptance Scenarios**:

1. **Given** a valid paid event for the correct attempt, **When** processed, **Then** payment becomes paid and the order is confirmed only if stock remains reserved or can be re-reserved.
2. **Given** an invalid signature or mismatched identity/amount, **When** received, **Then** no paid or fulfillment state is granted.
3. **Given** a verified late paid event after stock release, **When** it is processed, **Then** the payment remains recorded and the order enters a recoverable stock/refund exception if re-reservation fails.

### Edge Cases

- A callback acknowledged before worker processing survives a crash and is eventually processed or visible as an exception.
- Out-of-order failed and paid events cannot move a paid attempt backwards.
- Retry after provider timeout queries known status before creating another payment session.
- The same event ID from different provider accounts must not collide or be treated as one event.

## Requirements

### Functional Requirements

- **FR-001**: Online payment options MUST remain unavailable until a provider account, accepted method, currency, and commercial terms are approved.
- **FR-002**: Every online order MUST have a distinct payment attempt with amount, currency, expiry, provider account, and stable request identity.
- **FR-003**: Payment session creation MUST be recoverable and idempotent after process or provider failure.
- **FR-004**: A callback MUST be authenticated before acknowledgement and durably recorded with a deduplication identity including provider and account.
- **FR-005**: A verified event MUST match merchant/account, reference, amount, and currency before changing payment or order state.
- **FR-006**: Payment state progression MUST be monotonic; duplicate, delayed, or out-of-order events MUST not duplicate confirmation, reservation, or notification.
- **FR-007**: Paid orders MUST retain or regain valid stock before fulfillment; paid-without-stock MUST become a visible refund exception.
- **FR-008**: Staff status verification MUST use the same validation and transition rules as a provider callback.
- **FR-009**: Sensitive provider payloads MUST be redacted from staff views and audit output while retaining sufficient dispute evidence.
- **FR-010**: Each verified provider event MUST retain provider/account identity, provider occurrence time when supplied, local receipt time, and trusted application time separately; only one applied transition per deduplicated event may contribute to payment reporting.

### Key Entities

- **Payment attempt and event**: Order-linked amount, provider identity, current state, and trusted event history.
- **Callback receipt**: Authenticated, deduplicated provider event awaiting or recording processing outcome.
- **Payment exception**: Mismatched, late, or paid-without-stock outcome requiring staff action.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of invalid or mismatched callbacks leave orders unconfirmed.
- **SC-002**: Replaying an accepted callback 100 times produces one payment transition and one corresponding order effect.
- **SC-003**: Every acknowledged callback is either processed or appears in a recoverable exception queue after a worker interruption.
- **SC-004**: Replaying or delaying a callback does not change collected-payment totals twice or assign an unverified event to a cash period.

## Assumptions

- The merchant chooses an approved provider and confirms enabled methods, fees, refund terms, and test credentials before this payment path can launch.
- COD and pickup are separate payment paths; this feature does not treat a customer browser redirect as proof of collection.
