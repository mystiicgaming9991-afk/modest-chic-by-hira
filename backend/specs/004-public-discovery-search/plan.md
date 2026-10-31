# Implementation Plan: public discovery and search

**Status**: Implemented and integrated with the storefront (reviewed 2026-10-25).

- Public API and storefront support published-product browse/search, category and collection, fabric/color, price, sale, and stock filters.
- Sorting is deterministic for newest, price, and fulfilled-unit popularity; results use stable cursor pagination.
- Public routes hide unpublished products and inactive memberships. Query contracts cover browse and search filters; frontend controls expose the supported filters and sorting.
- Public product projections include the ordered published category membership list as well as the primary category, so storefront local filters and counts handle products assigned to more than one category.
- Remaining related gaps: product media hosting and operational inventory exception workflows are recorded in the integration review.
