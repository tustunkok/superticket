"""Comment endpoints for tickets."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_current_active_user, get_db
from superticket.models.user import User
from superticket.schemas.comment import CommentCreate, CommentOut
from superticket.services.comment import CommentService
from superticket.services.ticket import TicketService

router = APIRouter(tags=["comments"])


@router.post("/tickets/{ticket_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    ticket_id: str,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CommentOut:
    """Add a comment to a ticket."""
    # Verify ticket exists
    TicketService.get(db, ticket_id)
    comment = CommentService.create(
        session=db,
        ticket_id=ticket_id,
        author_id=current_user.id,
        author_name=current_user.full_name,
        content=data.content,
        is_internal=data.is_internal,
    )
    return comment


@router.get("/tickets/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(
    ticket_id: str,
    include_internal: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CommentOut]:
    """List comments for a ticket."""
    # Verify ticket exists
    TicketService.get(db, ticket_id)
    return CommentService.list_for_ticket(
        db, ticket_id, include_internal=include_internal, skip=skip, limit=limit
    )
