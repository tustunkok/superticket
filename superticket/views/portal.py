"""Self-service portal web views."""

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_current_active_user_from_cookie, get_db
from superticket.core.exceptions import TicketClosed
from superticket.core.flash import set_flash
from superticket.models.user import User
from superticket.services.comment import CommentService
from superticket.services.ticket import TicketService
from superticket.template_engine import templates

router = APIRouter(prefix="/portal", tags=["portal"])


async def _run_triage(ticket_id: str) -> None:
    from superticket.db.engine import session_factory as sf
    from superticket.services.triage import triage_ticket

    await triage_ticket(ticket_id, sf)


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
    total = TicketService.count(db, requester_id=str(current_user.id))
    paginated = TicketService.list_(db, requester_id=str(current_user.id), skip=skip, limit=limit)
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
    bg_tasks: BackgroundTasks,
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
    bg_tasks.add_task(_run_triage, ticket.id)
    set_flash(request, f"Ticket {ticket.id} created successfully.", "success")
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
        set_flash(request, "Cannot add comments to a closed ticket.", "error")
        return RedirectResponse(
            url=f"/portal/tickets/{ticket_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    set_flash(request, "Comment added successfully.", "success")
    return RedirectResponse(url=f"/portal/tickets/{ticket_id}", status_code=status.HTTP_303_SEE_OTHER)
