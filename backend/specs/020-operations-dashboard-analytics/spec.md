# Feature Specification: Operations Dashboard and Analytics

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.6, 8.8; `BACKEND_HLD.md` §8; `PRD.md` §§10, 12, 16; STORY-019, TASK-010.

## User Scenarios & Testing

### User Story 1 - See Today's Work (Priority: P1)

Authorized staff can see pending confirmation, packing, booking, payment, delivery, return, refund, and stock exception queues with counts that lead to actionable records.

**Independent Test**: Create one record in each representative queue and verify its dashboard count links to the same filtered list.

**Acceptance Scenarios**:

1. **Given** eligible open work, **When** staff open the dashboard, **Then** each count matches its underlying authorized queue.
2. **Given** staff lacking a domain permission, **When** they open the dashboard, **Then** private records and disallowed metrics are hidden or denied.

### User Story 2 - Understand Sales and Cash (Priority: P1)

The owner can compare order intake, COD confirmation, paid online orders, fulfilled orders, refunds, and settled cash without treating them as one sales number.

**Independent Test**: Create a placed COD order, a paid online order, a delivered COD order, and a settled remittance; verify each metric includes only its qualifying event.

**Acceptance Scenarios**:

1. **Given** orders at distinct lifecycle stages, **When** a date range is selected, **Then** intake, confirmed sales, collected payment, and settled cash remain separately labeled.
2. **Given** an exact event retry, **When** analytics are recalculated, **Then** the same business outcome is counted once.

### Edge Cases

- Date boundaries use one documented business time zone while stored events retain exact timestamps.
- A late refund changes net reporting in the correct period without rewriting the original order value.
- Dashboard counts are not built from unconsented marketing events when canonical commerce records exist.
- No PII export or detailed customer metrics are shown without permission and consent.
- Provider events may be observed later than they occurred; reports expose a documented period rule and do not silently rewrite previously issued snapshots.
- Customer merges, catalog archival, partial refunds, and repeated callbacks do not duplicate or erase historical financial facts.

## Requirements

### Functional Requirements

- **FR-001**: The dashboard MUST present actionable counts for COD confirmation, packing, booking, payment and delivery exceptions, low stock, pending returns/refunds, and unmatched settlements.
- **FR-002**: Every count MUST reconcile with the corresponding filtered staff list under the same data and time window.
- **FR-003**: Reporting MUST separately define placed order value, confirmed order value, collected payment, refunds, courier COD collection, and bank-settled cash.
- **FR-004**: Operational metrics MUST derive from authoritative business records and deduplicate retried events.
- **FR-005**: Staff access MUST respect current domain permissions; export of customer-level data MUST respect permission and consent.
- **FR-006**: Marketing attribution and funnel events MUST retain source/campaign identity without equating a placed COD order to collected revenue.
- **FR-007**: Date filters and currency presentation MUST be consistent across dashboard, lists, and exports.
- **FR-008**: Each metric MUST publish its grain, canonical source, qualifying transition, amount, currency, event/effective time, `Asia/Karachi` bucket rule, and correction/late-arrival behavior. Queue counts MUST identify whether they are current-state counts rather than historical facts.
- **FR-009**: Financial and operational reports MUST reconcile to authorized drill-down rows under one consistent data snapshot; any cached summary MUST expose its refresh watermark and be rebuildable from canonical records.
- **FR-010**: Analytics storage and exports MUST exclude credentials, access tokens, raw contact/address data, and unconsented marketing observations; customer-level drill-down and export require separate permission.

### Key Entities

- **Operational queue**: Filtered set of work requiring staff action.
- **Business metric**: Named calculation with source events, time window, and PKR minor-unit amount.
- **Attribution event**: Consent-aware campaign or funnel observation distinct from canonical sales.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every displayed queue count equals the number of records in its linked filter during an unchanged snapshot.
- **SC-002**: Replayed payment or order events do not change a completed metric more than once.
- **SC-003**: A manager can identify the highest-priority open operational queue within one dashboard visit.
- **SC-004**: For a seeded lifecycle covering placement, payment, partial refund, COD collection, and bank settlement, each distinct KPI equals the sum of its qualifying source rows, including across date boundaries and a late provider event.
- **SC-005**: A rebuilt reporting projection, if used, matches canonical totals after event retries and never exposes customer-level data to a staff member without permission.

## Assumptions

- The business approves precise KPI meanings, time zone, and attribution rules before final reports are treated as financial statements.
- Early dashboard slices may have fewer queues; each shown count must still be accurate and permission-safe.
