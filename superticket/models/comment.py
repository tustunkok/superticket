"""SQLAlchemy ORM comment model."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from superticket.db.base import Base

if TYPE_CHECKING:
    from superticket.models.ticket import Ticket


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Comment(Base):
    """Comment thread entries for tickets (public or internal)."""

    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="comments")

    def __repr__(self) -> str:
        return f"<Comment(id={self.id!r}, ticket_id={self.ticket_id!r}, internal={self.is_internal!r})>"
