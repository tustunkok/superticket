"""Ticket business logic & state machine enforcement."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from superticket.core.exceptions import InvalidStateTransition, TicketNotFound
from superticket.models.enums import TicketState
from superticket.models.ticket import AuditLog, Ticket
from superticket.services.state_machine import transition


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketService:
    """Encapsulates ticket CRUD, state transitions, and audit logging."""

    @staticmethod
    def create(
        session: Session,
        *,
        id: str,
        requester_id: str,
        category: str,
        sub_category: str,
        item: str,
        urgency: str,
        impact: str,
        priority: str,
    ) -> Ticket:
        """Create a new ticket in the `NEW` state and log the creation."""
        ticket = Ticket(
            id=id,
            requester_id=requester_id,
            category=category,
            sub_category=sub_category,
            item=item,
            urgency=urgency,
            impact=impact,
            priority=priority,
            state=TicketState.NEW.value,
        )
        session.add(ticket)
        session.flush()

        log = AuditLog(
            ticket_id=ticket.id,
            action="created",
            old_value=None,
            new_value={
                "id": ticket.id,
                "requester_id": ticket.requester_id,
                "category": ticket.category,
                "sub_category": ticket.sub_category,
                "item": ticket.item,
                "urgency": ticket.urgency,
                "impact": ticket.impact,
                "priority": ticket.priority,
                "state": ticket.state,
            },
        )
        session.add(log)
        session.commit()
        return ticket

    @staticmethod
    def get(session: Session, ticket_id: str) -> Ticket:
        """Retrieve a ticket by unique identifier."""
        ticket = session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar_one_or_none()
        if ticket is None:
            raise TicketNotFound(ticket_id)
        return ticket

    @staticmethod
    def list_(session: Session, *, skip: int = 0, limit: int = 100) -> list[Ticket]:
        """Paginated listing of tickets ordered by newest first."""
        result = session.execute(
            select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def update(
        session: Session,
        ticket_id: str,
        *,
        performed_by: str | None = None,
        **fields: Any,
    ) -> Ticket:
        """Update mutable ticket fields and record an audit entry."""
        ticket = TicketService.get(session, ticket_id)

        allowed_fields = {
            "category",
            "sub_category",
            "item",
            "urgency",
            "impact",
            "priority",
        }
        changes: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed_fields:
                raise ValueError(f"Field '{key}' is not mutable.")
            old = getattr(ticket, key)
            if old != value:
                changes[key] = {"old": old, "new": value}
                setattr(ticket, key, value)

        if changes:
            ticket.updated_at = _utc_now()
            log = AuditLog(
                ticket_id=ticket.id,
                action="updated",
                old_value={k: v["old"] for k, v in changes.items()},
                new_value={k: v["new"] for k, v in changes.items()},
                performed_by=performed_by,
            )
            session.add(log)
            session.commit()
        else:
            session.commit()

        return ticket

    @staticmethod
    def transition_state(
        session: Session,
        ticket_id: str,
        target_state: TicketState,
        *,
        performed_by: str | None = None,
    ) -> Ticket:
        """Attempt a state transition and record it in the audit log."""
        ticket = TicketService.get(session, ticket_id)
        current = TicketState(ticket.state)

        new_state = transition(current, target_state)

        old_state = ticket.state
        ticket.state = new_state.value
        ticket.updated_at = _utc_now()

        log = AuditLog(
            ticket_id=ticket.id,
            action="state_transition",
            old_value={"state": old_state},
            new_value={"state": ticket.state},
            performed_by=performed_by,
        )
        session.add(log)
        session.commit()
        return ticket
