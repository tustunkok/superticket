"""SQLAlchemy ORM model for triage override logging (AI feedback loop)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from superticket.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TriageOverrideLog(Base):
    """Records ground-truth data when a human overrides an AI triage suggestion.

    Used for building evaluation datasets and future model fine-tuning.
    """

    __tablename__ = "triage_override_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False)

    ai_category: Mapped[str | None] = mapped_column(String, nullable=True)
    human_category: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_sub_category: Mapped[str | None] = mapped_column(String, nullable=True)
    human_sub_category: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_item: Mapped[str | None] = mapped_column(String, nullable=True)
    human_item: Mapped[str | None] = mapped_column(String, nullable=True)

    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="triage_overrides")  # type: ignore[name-defined] # noqa: F821

    def __repr__(self) -> str:
        return f"<TriageOverrideLog(id={self.id!r}, ticket_id={self.ticket_id!r})>"
