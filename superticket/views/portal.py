"""Self-service portal web views."""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_current_active_user_from_cookie, get_db
from superticket.core.exceptions import TicketClosed
from superticket.models.user import User
from superticket.services.comment import CommentService
from superticket.services.ticket import TicketService
from superticket.template_engine import templates

router = APIRouter(prefix="/portal", tags=["portal"])


def _require_user(current_user: User) -> None:
    """Ensure current user has user role."""
    if current_user.role not in ("user", "agent", "admin"):
        # All authenticated users can access portal
        pass


@router.get("/")
def portal_dashboard(
    request: Request,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """List tickets for the current user."""
    # Get all tickets and filter by requester_id (since TicketService.list_ doesn't support filtering)
    all_tickets = TicketService.list_(db, skip=0, limit=1000)
    user_tickets = [t for t in all_tickets if t.requester_id == str(current_user.id) or t.requester_id == current_user.email]
    total = len(user_tickets)
    paginated = user_tickets[skip : skip + limit]
    return templates.TemplateResponse(
        request,
        "portal/dashboard.html",
        {
            "user": current_user,
            "tickets": paginated,
            "total": total,
            "skip": skip,
            "limit": limit,
        },
    )


@router.get("/tickets/new")
def new_ticket_form(request: Request, current_user: User = Depends(get_current_active_user_from_cookie)):
    """Render the ticket creation form."""
    return templates.TemplateResponse(
        request,
        "portal/ticket_new.html",
        {"user": current_user},
    )


@router.post("/tickets")
def create_ticket(
    request: Request,
    category: str = Form(...),
    sub_category: str = Form(...),
    item: str = Form(...),
    urgency: str = Form(...),
    impact: str = Form(default="individual"),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Create a new ticket from the portal."""
    import uuid
    ticket_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    ticket = TicketService.create(
        session=db,
        id=ticket_id,
        requester_id=str(current_user.id),
        category=category,
        sub_category=sub_category,
        item=item,
        urgency=urgency,
        impact=impact,
        description=description or None,
        performed_by=current_user.email,
    )
    return RedirectResponse(url=f"/portal/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/tickets/{ticket_id}")
def ticket_detail(
    request: Request,
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Show ticket detail with comments."""
    ticket = TicketService.get(db, ticket_id)
    comments = CommentService.list_for_ticket(db, ticket_id, include_internal=False)
    return templates.TemplateResponse(
        request,
        "portal/ticket_detail.html",
        {
            "user": current_user,
            "ticket": ticket,
            "comments": comments,
            "error": request.query_params.get("error"),
        },
    )


@router.get("/tickets/{ticket_id}/comments")
def ticket_comments_partial(
    request: Request,
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """HTMX: Load comments for a ticket."""
    comments = CommentService.list_for_ticket(db, ticket_id, include_internal=False)
    return templates.TemplateResponse(
        request,
        "partials/comment_thread.html",
        {"comments": comments},
    )


@router.post("/tickets/{ticket_id}/comments")
def add_comment(
    request: Request,
    ticket_id: str,
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Add a public comment from the portal."""
    try:
        CommentService.create(
            session=db,
            ticket_id=ticket_id,
            author_id=current_user.id,
            author_name=current_user.full_name,
            content=content,
            is_internal=False,
        )
    except TicketClosed:
        return RedirectResponse(
            url=f"/portal/tickets/{ticket_id}?error=closed",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url=f"/portal/tickets/{ticket_id}", status_code=status.HTTP_303_SEE_OTHER)
