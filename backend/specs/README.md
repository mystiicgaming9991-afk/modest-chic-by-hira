# Modest Chic specification map

**Scope:** The reviewed backend PRD, TRD, HLD, LLD, the product PRD, and `MASTER_BACKLOG.md`. This is the complete specification inventory for the V1 commerce plan. Feature specs, plans, contracts, tasks, and implementation now exist across the inventory; each feature's plan and the integration review record implemented behavior and remaining release gates. A listed spec or persistence model alone is not evidence that its workflow is complete.

The source of truth for cross-feature invariants is `BACKEND_PRD.md` §§6–8 and `BACKEND_TRD.md` §§4, 7, 11. Each feature specification owns its user outcome and acceptance criteria. Its plan and convergence evidence must reconcile contracts, migrations, code, and tests with the existing authentication and commerce foundation. Release gates below distinguish implemented workflows from external approvals and production evidence that are still outstanding.

| Order | Feature | Backlog coverage | Prerequisites | Release gate |
|---|---|---|---|---|
| 001 | [Staff authentication](001-staff-authentication/spec.md) | TASK-005, TASK-007 | None | Finish open auth acceptance tasks |
| 002 | [Commerce foundation and policies](002-commerce-foundation-policies/spec.md) | TASK-001, TASK-002, TASK-004, TASK-007 | 001 | Approve business policies before affected flows |
| 003 | [Catalog administration](003-catalog-administration/spec.md) | STORY-001 | 001, 002 | Supply real SKU content |
| 004 | [Public discovery and search](004-public-discovery-search/spec.md) | STORY-003, STORY-004, TASK-009 | 003 | Published content only |
| 005 | [Inventory and reservations](005-inventory-reservations/spec.md) | STORY-002 | 002, 003 | Opening stock and reservation settings |
| 006 | [Customer profiles and consent](006-customer-profiles-consent/spec.md) | STORY-012, privacy rules | 002 | Retention and consent approval |
| 007 | [Guest cart](007-guest-cart/spec.md) | STORY-005 | 003, 005 | Guest browser security |
| 008 | [Coupons and creator codes](008-coupons-creator-codes/spec.md) | STORY-016 | 003, 006 | Campaign terms |
| 009 | [Order core and manual sales](009-order-core-manual-sales/spec.md) | STORY-007 | 002, 003, 005, 006 | Order states and snapshots |
| 010 | [Guest checkout](010-guest-checkout/spec.md) | STORY-006 | 005, 007, 008, 009 | Shipping and pickup prices |
| 011 | [COD confirmation](011-cod-confirmation/spec.md) | STORY-008 | 009, 010 | Confirmation policy |
| 012 | [Online payments and callbacks](012-online-payments-callbacks/spec.md) | STORY-009, TASK-006 | 009, 010 | Approved merchant/provider contract |
| 013 | [Fulfillment and pickup](013-fulfillment-pickup/spec.md) | STORY-010 | 005, 009, 011, 012 | Courier and pickup terms |
| 014 | [Guest order access and tracking](014-guest-order-access-tracking/spec.md) | STORY-011 | 009, 013 | Private access and tracking checks |
| 015 | [Returns and exchanges](015-returns-exchanges/spec.md) | STORY-013 | 005, 009, 013, 014 | Return and exchange policy |
| 016 | [Refunds](016-refunds/spec.md) | STORY-014 | 012, 015 | Refund approval and manual evidence |
| 017 | [Settlement reconciliation](017-settlement-reconciliation/spec.md) | STORY-015 | 012, 013, 016 | Tax/withholding treatment |
| 018 | [Product reviews](018-product-reviews/spec.md) | STORY-017 | 004, 009, 014 | Moderation policy |
| 019 | [Customer notifications](019-customer-notifications/spec.md) | STORY-018 | 009, 013, 015, 016 | Approved templates and consent |
| 020 | [Operations dashboard and analytics](020-operations-dashboard-analytics/spec.md) | STORY-019, TASK-010 | 009, 012, 013, 017 | KPI definitions |
| 021 | [Deployment and recovery](021-deployment-recovery/spec.md) | TASK-003, TASK-008, TASK-012 | 002; applied throughout | Business-owned accounts and recovery exercise |
| 022 | [Storefront and admin integration](022-storefront-admin-integration/spec.md) | STORY-003–006, TASK-009, TASK-010, TASK-011 | 001, 004, 007, 010, 014, 018, 024 | Mobile, accessibility, SEO, analytics |
| 023 | [Staff access administration](023-staff-access-administration/spec.md) | TASK-005-B, TASK-005-C | 001; plan early | Preserve an active owner |
| 024 | [Customer email OTP login](024-customer-email-login/spec.md) | STORY-020 | 002, 006, 014; plan before 022 | OTP verification and account isolation |

## Backend module coverage

| Reviewed TRD domain | Feature owner |
|---|---|
| Identity, roles, sessions, audit | 001, 023; customer identity and sessions are 024 |
| Store settings and policy versions | 002 |
| Customers and consent | 006, 024 |
| Products, variants, categories, collections, media | 003; public discovery is 004 |
| Inventory balances, movements, reservations | 005 |
| Guest cart | 007 |
| Orders, items, events, guest access | 009, 010, 011, 014; account order claims are 024 |
| Payment attempts, callbacks, refunds | 012, 016 |
| Shipments, tracking, pickups | 013, 014 |
| Returns and exchanges | 015 |
| Coupons and redemptions | 008 |
| Settlement batches and lines | 017 |
| Notifications, durable events, provider callbacks | 001 foundation, 012, 013, 019, 021; customer sign-in email is 024 |
| Reviews | 018 |

## Existing slice compatibility

The initial authentication slice predates the commerce feature specs. The commerce
foundation reconciles its outbox and shared API error contract with that slice.
Continue preserving existing staff, session, audit, and email records when adding
features; extend the durable outbox instead of creating a competing one, and retain
the existing sign-in behavior.

## Shared rules for later plans

- One order, payment, shipment, return, and refund lifecycle has a single authoritative owner; other features call that owner's service rather than inventing another state machine.
- All prices, discounts, shipping, refunds, settlements, and totals use PKR integer minor units. Orders retain the customer-facing price, item, policy, and address snapshots present when accepted.
- Checkout and every competing writer take coupon, sorted inventory, then order locks in the documented order. Idempotency and durable event publication are part of the same state transition.
- COD, paid online, and approved pickup terms have different confirmation and fulfillment gates. Browser redirects, unverified callbacks, and courier timeouts never authorize fulfillment.
- Guest order credentials are bound to one order and to explicit read, return, and review scopes. Staff permissions and current account status are checked on protected actions.
- Customer email OTP accounts are optional alongside guest checkout. Shoppers enter a one-time code sent by email; no shopper sign-in link or password is offered. Staff retain email-and-password login. The two session types are separate, and a matching checkout email never grants access to a guest order without order-specific proof.
- External payments, courier bookings, and notifications must survive retries and crashes without duplicate business effects. Provider selection remains a release gate, not a guessed default.
- Every commerce feature must design reportable records before its migration: stable entity links, immutable accepted terms, deduplicated transitions, trusted event/effective and recorded times, typed non-sensitive dimensions, and measured indexes. Current-state fields serve queues; canonical history serves financial trends. Follow `BACKEND_TRD.md` §6.4, and keep marketing telemetry separate and consent-gated. Feature 020 consumes these records; it must not repair missing history later.
- Each feature follows the backend constitution's red-test, minimal implementation, green-test, refactor cycle. Generate its plan, data model, contracts, tasks, and convergence evidence **when that feature is selected**, then code that feature before moving to the next.

## Open business decisions

The source documents leave payment/courier selection, customer shipping prices, pickup payment terms, tax/withholding, return and exchange economics, retention/consent rules, and real catalog/stock data to business approval. Specs describe fail-closed behavior until an approved setting or policy exists; they do not assume commercial values.

## Customer login scope update

Feature 024 incorporates the later decision to offer customer login through an emailed OTP code only. It supersedes earlier guest-only and customer-account-deferral statements and the intervening customer-password and sign-in-link assumptions. Guest checkout remains available and does not require an account. Its implementation keeps customer identity, OTP challenges, customer sessions, and order claims separate from staff credentials, and never grants guest-order access based only on a contact match; see the 024 plan and integration review for test evidence and the live-email release gate.
