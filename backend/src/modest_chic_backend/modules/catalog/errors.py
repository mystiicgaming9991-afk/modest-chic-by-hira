"""Catalog-specific application errors."""


class CatalogStaleEditError(ValueError):
    """An edit was based on a product or variant version that has changed."""
