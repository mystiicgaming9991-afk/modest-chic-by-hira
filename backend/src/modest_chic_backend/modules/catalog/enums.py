"""Shared catalog enumeration types."""

import enum


class ProductStatus(enum.StrEnum):
    """Publication lifecycle for products, categories, and media."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"
