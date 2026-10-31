"""Pydantic request/response schemas for policy versions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyVersionPublish(BaseModel):
    """Request body for publishing a new policy version."""

    type: str = Field(min_length=1, max_length=100)
    effective_from: datetime
    content: dict[str, Any]


class PolicyVersionRead(BaseModel):
    """Response body for a policy version."""

    id: UUID
    type: str
    version: int
    effective_from: datetime
    content: dict[str, Any]
    approved_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyVersionListResponse(BaseModel):
    """Wrapper for the list of policy versions."""

    items: list[PolicyVersionRead]


# Valid policy types per BACKEND_TRD.md §4.2.2
VALID_POLICY_TYPES = {
    "checkout_bundle",
    "returns",
    "shipping",
    "privacy",
    "terms",
    "cod_confirmation",
}


def validate_policy_type(type: str) -> None:
    """Raise ValueError if the policy type is not recognized."""
    if type not in VALID_POLICY_TYPES:
        raise ValueError(
            f"unknown policy type: {type}. Must be one of: {', '.join(sorted(VALID_POLICY_TYPES))}"
        )
