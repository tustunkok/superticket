"""Admin user management views."""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID

from superticket.core.dependencies import require_admin_cookie, get_db
from superticket.models.enums import UserRole
from superticket.models.user import User
from superticket.services.auth import AuthService
from superticket.template_engine import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    request: Request,
    role: str = None,
    is_active: str = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """List all users with optional filters."""
    active_filter = None
    if is_active == "active":
        active_filter = True
    elif is_active == "inactive":
        active_filter = False

    users, total = AuthService.list_users(
        db, skip=skip, limit=limit, role=role, is_active=active_filter
    )

    return templates.TemplateResponse(
        request,
        "admin/user_list.html",
        {
            "user": current_user,
            "users": users,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter_role": role,
            "filter_active": is_active,
            "roles": [r.value for r in UserRole],
        },
    )


@router.post("/users/{user_id}/role")
def update_role(
    user_id: str,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """Update a user's role."""
    try:
        AuthService.update_user_role(db, UUID(user_id), role)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/users?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/admin/users?success=Role+updated", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/toggle-active")
def toggle_active(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """Toggle a user's active status."""
    try:
        user = AuthService.get_user(db, UUID(user_id))
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        AuthService.set_user_active(db, UUID(user_id), not user.is_active, current_user)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/users?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/admin/users?success=Status+updated", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """Delete a user."""
    try:
        AuthService.delete_user(db, UUID(user_id), current_user)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/users?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/admin/users?success=User+deleted", status_code=status.HTTP_303_SEE_OTHER)
