"""Pydantic schemas for comments."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CommentCreate(BaseModel):
    """Fields required to create a comment."""

    content: str
    is_internal: bool = False


class CommentOut(BaseModel):
    """Read-only comment representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: str
    author_id: uuid.UUID
    author_name: str
    content: str
    is_internal: bool
    created_at: datetime
