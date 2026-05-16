"""SQLAlchemy ORM models for SuperTicket."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from superticket.db.base import Base
from superticket.models.enums import TicketState

if TYPE_CHECKING:
    from superticket.models.comment import Comment


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    """Core ticketing entity."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requester_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    sub_category: Mapped[str] = mapped_column(String, nullable=False)
    item: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[str] = mapped_column(String, nullable=False)
    impact: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default=TicketState.NEW.value)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="ticket", cascade="all, delete-orphan", lazy="selectin"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="ticket", cascade="all, delete-orphan", lazy="selectin", order_by="Comment.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id!r}, state={self.state!r})>"


class AuditLog(Base):
    """Immutable audit trail for ticket changes."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    performed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id!r}, action={self.action!r})>"
