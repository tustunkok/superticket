"""Web authentication routes (cookie-based)."""

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_db
from superticket.core.exceptions import InvalidCredentials
from superticket.services.auth import AuthService, create_access_token
from superticket.template_engine import templates

router = APIRouter(tags=["web-auth"])


@router.get("/login")
def login_page(request: Request, error: str = None):
    """Render the login form."""
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
    )


@router.post("/login")
def login_submit(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Authenticate user and set JWT cookie."""
    try:
        user = AuthService.authenticate_user(db, email, password)
    except InvalidCredentials:
        return RedirectResponse(
            url="/login?error=Invalid+email+or+password",
            status_code=status.HTTP_303_SEE_OTHER,
        )

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


@router.get("/logout")
def logout():
    """Clear the JWT cookie and redirect to login."""
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(key="access_token", path="/")
    return resp
