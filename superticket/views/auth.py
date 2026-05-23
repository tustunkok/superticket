"""Web authentication routes (cookie-based)."""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_db
from superticket.core.exceptions import InvalidCredentials
from superticket.core.flash import set_flash
from superticket.services.auth import AuthService, create_access_token
from superticket.template_engine import templates

router = APIRouter(tags=["web-auth"])


@router.get("/login")
def login_page(request: Request):
    """Render the login form."""
    return templates.TemplateResponse(
        request,
        "login.html",
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Authenticate user and set JWT cookie."""
    try:
        user = AuthService.authenticate_user(db, email, password)
    except InvalidCredentials:
        set_flash(request, "Invalid email or password.", "error")
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    redirect_url = "/portal/" if user.role == "user" else "/agent/"
    resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,
        path="/",
        samesite="lax",
    )
    return resp


@router.get("/register")
def register_page(request: Request, error: str = None):
    """Render the registration form."""
    return templates.TemplateResponse(
        request,
        "register.html",
        {"error": error},
    )


@router.post("/register")
def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(min_length=6),
    db: Session = Depends(get_db),
):
    """Create a new user account and redirect to login."""
    try:
        AuthService.register_user(db, email=email, password=password, full_name=full_name)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": f"Email '{email}' is already registered."},
            status_code=status.HTTP_409_CONFLICT,
        )

    set_flash(request, "Account created. Please sign in.", "info")
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout():
    """Clear the JWT cookie and redirect to login."""
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(key="access_token", path="/")
    return resp
