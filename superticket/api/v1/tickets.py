"""Ticket CRUD & state transition endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_db
from superticket.schemas.ticket import (
    AuditLogOut,
    TicketCreate,
    TicketListOut,
    TicketOut,
    TicketTransition,
    TicketUpdate,
)
from superticket.services.ticket import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, db: Session = Depends(get_db)) -> TicketOut:
    """Create a new ticket."""
    try:
        ticket = TicketService.create(session=db, **data.model_dump())
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket with id '{data.id}' already exists.",
        ) from exc
    return ticket


@router.get("", response_model=TicketListOut)
def list_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> TicketListOut:
    """List tickets with pagination."""
    items = TicketService.list_(db, skip=skip, limit=limit)
    return TicketListOut(total=len(items), skip=skip, limit=limit, items=items)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> TicketOut:
    """Retrieve a single ticket by ID."""
    return TicketService.get(db, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    db: Session = Depends(get_db),
) -> TicketOut:
    """Update mutable ticket fields."""
    try:
        fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        return TicketService.update(db, ticket_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{ticket_id}/transition", response_model=TicketOut)
def transition_ticket(
    ticket_id: str,
    data: TicketTransition,
    db: Session = Depends(get_db),
) -> TicketOut:
    """Trigger a state transition on a ticket."""
    return TicketService.transition_state(
        db,
        ticket_id,
        data.target_state,
        performed_by=data.performed_by,
    )


@router.get("/{ticket_id}/audit", response_model=list[AuditLogOut])
def get_audit_log(ticket_id: str, db: Session = Depends(get_db)) -> list[AuditLogOut]:
    """Get the immutable audit log for a ticket."""
    ticket = TicketService.get(db, ticket_id)
    return ticket.audit_logs
