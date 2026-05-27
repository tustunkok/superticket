"""Triage API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_current_active_user, get_db
from superticket.models.enums import TicketState
from superticket.models.user import User
from superticket.schemas.ticket import TriageConfirmIn, TriageResult
from superticket.services.ticket import TicketService
from superticket.services.triage import confirm_triage

router = APIRouter(prefix="/tickets", tags=["triage"])


@router.get("/{ticket_id}/triage", response_model=TriageResult)
def get_triage(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get AI triage results for a ticket."""
    ticket = TicketService.get(db, ticket_id)
    if not ticket.ai_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No triage results available yet.",
        )
    return TriageResult(
        ai_category=ticket.ai_category,
        ai_sub_category=ticket.ai_sub_category,
        ai_item=ticket.ai_item,
        sentiment_score=ticket.sentiment_score,
        pii_detected=ticket.pii_detected,
        suggested_resolution=ticket.suggested_resolution,
        confidence_score=ticket.confidence_score,
    )


@router.post("/{ticket_id}/triage/confirm")
def confirm_triage_endpoint(
    ticket_id: str,
    data: TriageConfirmIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confirm or override AI triage results.

    If category/sub_category/item are not provided, the existing ticket values
    are used as the human confirmation. Any difference from AI suggestions is
    logged as a ground-truth override.
    """
    if current_user.role not in ("agent", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or admin access required.",
        )

    ticket = TicketService.get(db, ticket_id)
    if ticket.state != TicketState.TRIAGE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket is in state '{ticket.state}', not 'triage'.",
        )

    confirm_triage(
        db,
        ticket_id,
        category=data.category if data.category else None,
        sub_category=data.sub_category if data.sub_category else None,
        item=data.item if data.item else None,
        override_reason=data.override_reason,
        performed_by=current_user.email,
    )

    return {"detail": "Triage confirmed.", "ticket_id": ticket_id}
