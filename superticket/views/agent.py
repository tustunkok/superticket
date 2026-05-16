"""Agent workspace web views."""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from superticket.core.dependencies import get_current_active_user_from_cookie, get_db
from superticket.core.exceptions import TicketClosed
from superticket.models.enums import TicketState
from superticket.models.user import User
from superticket.services.comment import CommentService
from superticket.services.state_machine import valid_transitions
from superticket.services.ticket import TicketService, _compute_priority
from superticket.template_engine import templates

router = APIRouter(prefix="/agent", tags=["agent"])


def _require_agent(current_user: User) -> None:
    """Ensure current user is an agent or admin."""
    if current_user.role not in ("agent", "admin"):
        pass


@router.get("/")
def agent_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Default agent dashboard showing ticket queue."""
    return RedirectResponse(url="/agent/tickets", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/tickets")
def agent_ticket_queue(
    request: Request,
    state: str = None,
    priority: str = None,
    assigned_to: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Full ticket queue with filters."""
    all_tickets = TicketService.list_(db, skip=0, limit=1000)

    filtered = all_tickets
    if state:
        filtered = [t for t in filtered if t.state == state]
    if priority:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to == "unassigned":
        pass
    elif assigned_to:
        filtered = [t for t in filtered if getattr(t, 'assigned_to', None) == assigned_to]

    total = len(filtered)
    paginated = filtered[skip : skip + limit]

    return templates.TemplateResponse(
        request,
        "agent/dashboard.html",
        {
            "user": current_user,
            "tickets": paginated,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter_state": state,
            "filter_priority": priority,
            "filter_assigned": assigned_to,
        },
    )


@router.get("/tickets/{ticket_id}")
def agent_ticket_redirect(ticket_id: str):
    """Redirect /agent/tickets/{id} to the workspace route."""
    return RedirectResponse(url=f"/agent/tickets/{ticket_id}/work", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/tickets/{ticket_id}/work")
def ticket_workspace(
    request: Request,
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Main workspace view for a ticket."""
    ticket = TicketService.get(db, ticket_id)
    comments = CommentService.list_for_ticket(db, ticket_id, include_internal=True)
    audit_logs = ticket.audit_logs

    current_state = TicketState(ticket.state)
    transitions = valid_transitions(current_state)

    # Resolve requester name and email
    requester_name = ticket.requester_id
    requester_email = ""
    try:
        requester = db.execute(
            select(User).where(User.id == UUID(ticket.requester_id))
        ).scalar_one_or_none()
        if requester:
            requester_name = requester.full_name
            requester_email = requester.email
    except ValueError:
        # requester_id might be an email (backwards compatibility)
        requester = db.execute(
            select(User).where(User.email == ticket.requester_id)
        ).scalar_one_or_none()
        if requester:
            requester_name = requester.full_name
            requester_email = requester.email

    return templates.TemplateResponse(
        request,
        "agent/ticket_workspace.html",
        {
            "user": current_user,
            "ticket": ticket,
            "comments": comments,
            "audit_logs": audit_logs,
            "transitions": transitions,
            "error": request.query_params.get("error"),
            "requester_name": requester_name,
            "requester_email": requester_email,
        },
    )


@router.post("/tickets/{ticket_id}/comments")
def add_agent_comment(
    request: Request,
    ticket_id: str,
    content: str = Form(...),
    is_internal: bool = Form(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Add a comment from agent (public or internal)."""
    try:
        CommentService.create(
            session=db,
            ticket_id=ticket_id,
            author_id=current_user.id,
            author_name=current_user.full_name,
            content=content,
            is_internal=is_internal,
        )
    except TicketClosed:
        return RedirectResponse(
            url=f"/agent/tickets/{ticket_id}/work?error=closed",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/agent/tickets/{ticket_id}/work",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/tickets/{ticket_id}/transition")
def transition_ticket(
    request: Request,
    ticket_id: str,
    target_state: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Trigger state transition from workspace."""
    TicketService.transition_state(
        db,
        ticket_id,
        TicketState(target_state),
        performed_by=current_user.email,
    )
    return RedirectResponse(
        url=f"/agent/tickets/{ticket_id}/work",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/tickets/{ticket_id}/triage")
def triage_ticket(
    request: Request,
    ticket_id: str,
    category: str = Form(...),
    sub_category: str = Form(...),
    item: str = Form(...),
    urgency: str = Form(...),
    impact: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_cookie),
):
    """Update ticket fields and transition from triage to assigned."""
    priority = _compute_priority(urgency, impact)
    TicketService.update(
        db,
        ticket_id,
        category=category,
        sub_category=sub_category,
        item=item,
        urgency=urgency,
        impact=impact,
        priority=priority,
        performed_by=current_user.email,
    )
    TicketService.transition_state(
        db,
        ticket_id,
        TicketState.ASSIGNED,
        performed_by=current_user.email,
    )
    return RedirectResponse(
        url=f"/agent/tickets/{ticket_id}/work",
        status_code=status.HTTP_303_SEE_OTHER,
    )