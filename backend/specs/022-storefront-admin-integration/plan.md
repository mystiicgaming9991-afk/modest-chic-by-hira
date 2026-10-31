# Spec 022: Storefront and Admin Integration — Plan

**Status**: Core guest shopping and staff workspaces are integrated; business-dependent workflows and release sign-off remain (reviewed 2026-10-25).

## Verified integration

- The Next.js storefront reads public catalog and discovery data from the commerce API and connects guest cart, COD quote/checkout, private confirmation, and same-tab recovery through same-origin BFF routes.
- Customer email OTP, account history, explicit guest-order claims, marketing opt-out, and staff order/customer/catalog/inventory/promotion/settings/review workflows are connected to their permissioned APIs.
- Staff and customer credentials use separate HttpOnly cookie paths. Private order credentials are not placed in shareable query parameters. Mutations enforce same-origin checks in the BFF; staff mutations also use API CSRF proof.
- Published product and collection pages derive search/social titles and descriptions from catalog data; absolute canonical URLs use `NEXT_PUBLIC_SITE_URL`. Account, cart, wishlist, checkout, order confirmation, and staff pages are marked noindex.
- Checkout form controls have accessible names through associated labels, and transient customer-account load failures present an explicit retry rather than appearing as sign-out.
- The integration review documents implemented behavior, test evidence, and known open specification work: [INTEGRATION_REVIEW.md](../../../INTEGRATION_REVIEW.md).

## Remaining

- Finish or approve payment provider, courier, pickup, returns/refunds, settlement, and transactional notification workflows before exposing those paths.
- Configure media delivery and sign off the product and policy copy supplied to public metadata.
- Complete accessibility, narrow-screen, performance, SEO/indexing, and consent-aware analytics sign-off against product-owner criteria.
- Run critical journeys in the actual deployment environment; local tests/build do not establish production readiness.
