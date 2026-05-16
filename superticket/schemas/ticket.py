"""Pydantic request & response DTOs for tickets."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

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
    created_at: datetime
    updated_at: datetime


class TicketTransition(BaseModel):
    """Request body for a state transition."""

    target_state: TicketState


class TicketListOut(BaseModel):
    """Paginated list of tickets."""

    total: int
    skip: int
    limit: int
    items: list[TicketOut]
