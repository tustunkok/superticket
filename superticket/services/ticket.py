"""Ticket business logic & state machine enforcement."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from superticket.core.exceptions import TicketNotFound
from superticket.models.enums import TicketState
from superticket.models.ticket import AuditLog, Ticket
from superticket.models.user import User
from superticket.services.state_machine import transition


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_requester_id(session: Session, requester_id: str) -> str:
    """Resolve requester_id to a UUID string if it's an email or UUID.

    - If already a valid UUID, return as-is.
    - If an email, look up the user and return their UUID.
    - If neither, return the original value (backwards compatibility).
    """
    try:
        uuid_obj = UUID(requester_id)
        return str(uuid_obj)
    except ValueError:
        pass

    # Might be an email - look up user
    user = session.execute(
        select(User).where(User.email == requester_id)
    ).scalar_one_or_none()
    if user:
        return str(user.id)

    # Return as-is if we can't resolve
    return requester_id


def _compute_priority(urgency: str, impact: str) -> str:
    """Map urgency × impact to a priority code (P1–P4)."""
    urgency = urgency.lower()
    impact = impact.lower()
    matrix = {
        ("high", "org"): "P1",
        ("high", "dept"): "P2",
        ("high", "individual"): "P2",
        ("medium", "org"): "P2",
        ("medium", "dept"): "P3",
        ("medium", "individual"): "P3",
        ("low", "org"): "P3",
        ("low", "dept"): "P4",
        ("low", "individual"): "P4",
    }
    return matrix.get((urgency, impact), "P3")


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
        priority: str | None = None,
        description: str | None = None,
        performed_by: str | None = None,
    ) -> Ticket:
        """Create a new ticket in the `NEW` state and log the creation."""
        # Resolve requester_id to UUID if it's an email
        resolved_requester_id = _resolve_requester_id(session, requester_id)

        computed_priority = priority or _compute_priority(urgency, impact)
        ticket = Ticket(
            id=id,
            requester_id=resolved_requester_id,
            category=category,
            sub_category=sub_category,
            item=item,
            urgency=urgency,
            impact=impact,
            priority=computed_priority,
            state=TicketState.NEW.value,
            description=description,
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
                "description": ticket.description,
            },
            performed_by=performed_by,
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
    def count(session: Session, *, requester_id: str | None = None, state: str | None = None, priority: str | None = None, assigned_to: str | None = None) -> int:
        """Return the total number of tickets matching optional filter criteria."""
        stmt = select(func.count()).select_from(Ticket)
        if requester_id is not None:
            stmt = stmt.where(Ticket.requester_id == requester_id)
        if state is not None:
            stmt = stmt.where(Ticket.state == state)
        if priority is not None:
            stmt = stmt.where(Ticket.priority == priority)
        if assigned_to == "":
            stmt = stmt.where(Ticket.assigned_to.is_(None))
        elif assigned_to is not None:
            stmt = stmt.where(Ticket.assigned_to == assigned_to)
        result = session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def list_(session: Session, *, skip: int = 0, limit: int = 100, requester_id: str | None = None, state: str | None = None, priority: str | None = None, assigned_to: str | None = None) -> list[Ticket]:
        """Paginated listing of tickets ordered by newest first with optional SQL-level filters."""
        stmt = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
        if requester_id is not None:
            stmt = stmt.where(Ticket.requester_id == requester_id)
        if state is not None:
            stmt = stmt.where(Ticket.state == state)
        if priority is not None:
            stmt = stmt.where(Ticket.priority == priority)
        if assigned_to == "":
            stmt = stmt.where(Ticket.assigned_to.is_(None))
        elif assigned_to is not None:
            stmt = stmt.where(Ticket.assigned_to == assigned_to)
        result = session.execute(stmt.offset(skip).limit(limit))
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
            "description",
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
