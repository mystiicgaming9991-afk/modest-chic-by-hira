# Feature Specification: Catalog Administration

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§6.3, 7.6; `BACKEND_TRD.md` §4.4; `BACKEND_HLD.md` §3.1; STORY-001.

## User Scenarios & Testing

### User Story 1 - Maintain Products and Variants (Priority: P1)

Authorized catalog staff can create and revise products, sellable variants, SKU identity, descriptions, care details, and PKR prices before publishing them.

**Independent Test**: Create a draft with two variants, revise one price, publish it, and verify the correct current product data is visible to an authorized staff member.

**Acceptance Scenarios**:

1. **Given** a new product with valid unique SKU variants, **When** staff save it, **Then** it remains a draft until explicitly published.
2. **Given** an existing variant, **When** staff change its price, **Then** future listings use the new price and past orders retain their original price snapshot.
3. **Given** a duplicate SKU or slug, **When** staff save it, **Then** the change is rejected without altering the existing product.

### User Story 2 - Organize and Publish a Range (Priority: P1)

Staff can maintain categories, collections, ordered collection membership, and product imagery, and archive products without erasing historic orders.

**Independent Test**: Place a published product in a category and ordered collection, attach media, archive it, and verify it is hidden publicly while its staff record remains.

**Acceptance Scenarios**:

1. **Given** an authorized collection editor, **When** they reorder membership, **Then** customers see the approved order without duplicates.
2. **Given** an archived product, **When** a customer browses or searches, **Then** it is excluded from sellable results while existing order snapshots remain intact.

### Edge Cases

- Archived or unpublished variants cannot be added to new carts or orders.
- Deleting media referenced by another product or an active display must not leave a broken image.
- An image upload that fails validation leaves product publication and existing media unchanged.
- Concurrent edits to price or publication state must not silently lose either change.

## Requirements

### Functional Requirements

- **FR-001**: Staff with `catalog.write` MUST be able to create and update products, variants, categories, collections, and ordered collection membership.
- **FR-002**: Product slug and variant SKU MUST be unique; products MUST have explicit draft, published, and archived visibility states.
- **FR-003**: A published product MUST expose approved title, description, fabric, dimensions, care, media, and current variant price in PKR minor units.
- **FR-004**: Staff with `catalog.archive` MUST be able to archive a product without deleting order history or item snapshots.
- **FR-005**: Media records MUST have stable order and alternative text; invalid, unsafe, or failed uploads MUST not be published.
- **FR-006**: Catalog changes MUST record the actor and time and MUST reject stale conflicting updates.
- **FR-007**: Public availability MUST reflect current publication and variant state; stock quantity is owned by the inventory feature.

### Key Entities

- **Product and variant**: Sellable description, unique slug/SKU, publication state, attributes, and current price.
- **Category and collection**: Discovery grouping and ordered product membership.
- **Product media**: Approved image identity, display order, and alternative text.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Staff can create, review, and publish a two-variant product in under five minutes when content is ready.
- **SC-002**: 100% of duplicate SKU/slug submissions are rejected without changing an existing record.
- **SC-003**: 100% of archived or draft products are absent from public sellable results while historical order details remain available.

## Assumptions

- The business supplies approved copy, photography, SKU definitions, and prices before publication.
- Media storage and delivery are covered by the deployment and recovery feature.
- Inventory balances, public search, and reviews are separate features that consume catalog identities.
