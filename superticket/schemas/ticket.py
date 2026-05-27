"""Pydantic request & response DTOs for tickets."""

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from superticket.models.enums import TicketState


class AuditLogOut(BaseModel):
    """Read-only audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: str | uuid.UUID
    action: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any]
    performed_by: str | None
    timestamp: datetime


class TicketCreate(BaseModel):
    """Fields required to create a new ticket."""

    id: str
    requester_id: str
    category: str
    sub_category: str
    item: str
    urgency: str
    impact: str
    description: str | None = None


class TicketUpdate(BaseModel):
    """Mutable ticket fields."""

    model_config = ConfigDict(extra="forbid")

    category: str | None = None
    sub_category: str | None = None
    item: str | None = None
    urgency: str | None = None
    impact: str | None = None
    priority: str | None = None
    description: str | None = None


class TicketOut(BaseModel):
    """Read-only ticket representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    requester_id: str
    category: str
    sub_category: str
    item: str
    urgency: str
    impact: str
    priority: str
    state: str
    description: str | None = None
    ai_category: str | None = None
    ai_sub_category: str | None = None
    ai_item: str | None = None
    sentiment_score: float | None = None
    pii_detected: bool = False
    suggested_resolution: str | None = None
    confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime


class TicketTransition(BaseModel):
    """Request body for a state transition."""

    target_state: TicketState


class TriageResult(BaseModel):
    """AI triage results for a ticket."""

    ai_category: str | None = None
    ai_sub_category: str | None = None
    ai_item: str | None = None
    sentiment_score: float | None = None
    pii_detected: bool = False
    suggested_resolution: str | None = None
    confidence_score: float | None = None


class TriageConfirmIn(BaseModel):
    """Request body for confirming or overriding AI triage."""

    category: str | None = None
    sub_category: str | None = None
    item: str | None = None
    override_reason: str | None = None


class TicketListOut(BaseModel):
    """Paginated list of tickets."""

    total: int
    skip: int
    limit: int
    items: list[TicketOut]
