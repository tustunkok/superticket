"""Pydantic schemas for Knowledge Base."""

from pydantic import BaseModel, ConfigDict


class KBArticleOut(BaseModel):
    """Read-only KB article representation."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    category: str
    sub_category: str
    tags: list[str]
    content: str
