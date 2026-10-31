# Feature Specification: Settlement Reconciliation

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.6, 8.7; `BACKEND_TRD.md` §4.12; `BACKEND_LLD.md` §2.4; STORY-015.

## User Scenarios & Testing

### User Story 1 - Import Remittance Records (Priority: P1)

An authorized owner can import gateway and courier settlement batches and retain the source and bank/remittance reference used to investigate cash.

**Independent Test**: Import a batch twice using the same provider, account, and source reference; verify one batch and all original lines remain.

**Acceptance Scenarios**:

1. **Given** a valid external settlement file or record, **When** staff import it, **Then** gross, fees, withholding, adjustments, net, account, source, and bank references are preserved.
2. **Given** an exact duplicate source, **When** imported, **Then** it does not create another batch or line.

### User Story 2 - Resolve Cash Differences (Priority: P1)

Staff can match settlement lines to payments or COD shipments, see partial/unmatched/disputed amounts, and record a reasoned resolution.

**Independent Test**: Match one exact line, one partial line, and one unknown reference; verify their distinct states and variance totals.

**Acceptance Scenarios**:

1. **Given** a matching payment or shipment, **When** staff reconcile a line, **Then** calculated gross, fee, withholding, adjustment, and net differences are visible.
2. **Given** an unresolved or disputed line, **When** staff inspect the batch, **Then** it remains in an exception queue until a reasoned action is recorded.

### Edge Cases

- A courier's COD collection event is not treated as a bank remittance.
- One external line cannot be matched twice to overstate settled cash.
- Missing account or bank reference stays unresolved instead of guessing a match.
- Concurrent matching actions cannot produce two final owners for one line.

## Requirements

### Functional Requirements

- **FR-001**: Each imported batch MUST identify provider, account, source reference, period, currency, and bank/remittance reference when supplied.
- **FR-002**: Exact duplicate imports MUST be idempotent by provider, account, and source reference; changed duplicates MUST be flagged for review.
- **FR-003**: Every line MUST retain its external reference and integer minor-unit gross, fees, withholding, adjustments, and net figures.
- **FR-004**: Matching MUST validate the payment or shipment identity and expose exact, partial, unmatched, duplicate, and disputed states.
- **FR-005**: Staff resolution MUST record actor, time, reason, and any corrected link without rewriting the imported source figures.
- **FR-006**: Reported cash collected, cash settled, fees, withholding, and open variance MUST remain distinct metrics.
- **FR-007**: Tax and withholding categorization MUST follow an approved business/accounting rule before those amounts are represented as final tax obligations.
- **FR-008**: Bank-settled reporting MUST use a verified bank/remittance evidence time and unique source line identity, not batch import time, courier collection, or a mutable match status alone.

### Key Entities

- **Settlement batch and line**: Provider/account source, bank reference, source financial amounts, and matching state.
- **Match decision and exception**: Linked payment or shipment, variance, actor, and resolution history.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Exact repeated imports create zero duplicate batches or lines.
- **SC-002**: 100% of unmatched or partial lines remain visible until explicitly resolved.
- **SC-003**: Every resolved line can be traced to a source line, payment or shipment, actor, and variance calculation.
- **SC-004**: Re-importing or rematching the same source lines cannot increase settled-cash totals; a batch without bank evidence contributes zero bank-settled cash.

## Assumptions

- Finance approves tax, withholding, fee, and bank evidence rules; this feature does not calculate unspecified liabilities.
- Payment capture, courier COD collection, and bank settlement are separate events.
