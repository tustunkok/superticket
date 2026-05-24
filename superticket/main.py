"""FastAPI application factory & lifespan events."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from superticket.api.v1.auth import router as api_auth_router
from superticket.api.v1.comments import router as comments_router
from superticket.api.v1.tickets import router as tickets_router
from superticket.core.config import settings
from superticket.core.dependencies import get_optional_user_from_cookie
from superticket.core.exceptions import InvalidStateTransition, TicketClosed, TicketNotFound
from superticket.db.engine import init_db, SessionLocal
from superticket.models.user import User
from superticket.services.auth import hash_password
from superticket.template_engine import templates
from superticket.views import admin_router, agent_router, auth_router as web_auth_router, kb_router, portal_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup and seed default admin user."""
    init_db()
    _seed_default_admin()
    yield


def _seed_default_admin() -> None:
    """Create a default admin user if none exists."""
    db: Session = SessionLocal()
    try:
        exists = db.execute(
            select(User).where(User.email == "admin@superticket.local")
        ).scalar_one_or_none()
        if not exists:
            admin = User(
                email="admin@superticket.local",
                hashed_password=hash_password("admin"),
                full_name="Admin User",
                role="admin",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title="SuperTicket",
    description="High-Velocity Ticketing & Hybrid AI Triage",
    version=settings.app_version,
    lifespan=lifespan,
    redirect_slashes=False,
)

# Session middleware must be registered first so request.session is available everywhere
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)


@app.middleware("http")
async def unauthenticated_redirect_middleware(request: Request, call_next):
    """Redirect unauthenticated HTML requests to /login (GET only, no POST loop)."""
    response = await call_next(request)
    if response.status_code == 401:
        accept = request.headers.get("accept", "")
        is_api = request.url.path.startswith("/api/")
        if "text/html" in accept and not is_api:
            return RedirectResponse(url="/login", status_code=303)
    return response


# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API routes
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(api_auth_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(kb_router, prefix="/api/v1")

# Web UI routes
app.include_router(web_auth_router)
app.include_router(portal_router)
app.include_router(agent_router)
app.include_router(admin_router)


def _render_error_response(
    request: Request,
    exc: Exception,
    status_code: int,
    title: str,
    code: str,
):
    """Return HTML for browser requests, JSON for API requests."""
    accept = request.headers.get("accept", "")
    is_api = request.url.path.startswith("/api/")
    if "text/html" in accept and not is_api:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": status_code,
                "title": title,
                "message": str(exc),
                "code": code,
            },
            status_code=status_code,
        )
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "code": code},
    )


@app.exception_handler(TicketNotFound)
async def ticket_not_found_handler(request: Request, exc: TicketNotFound):
    return _render_error_response(request, exc, 404, "Not Found", "TICKET_NOT_FOUND")


@app.exception_handler(InvalidStateTransition)
async def invalid_state_transition_handler(request: Request, exc: InvalidStateTransition):
    return _render_error_response(request, exc, 400, "Invalid State Transition", "INVALID_STATE_TRANSITION")


@app.exception_handler(TicketClosed)
async def ticket_closed_handler(request: Request, exc: TicketClosed):
    return _render_error_response(request, exc, 403, "Ticket Closed", "TICKET_CLOSED")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
def root_redirect(
    current_user: User | None = Depends(get_optional_user_from_cookie),
):
    """Redirect root to login or dashboard based on auth status."""
    if current_user and current_user.is_active:
        if current_user.role in ("agent", "admin"):
            return RedirectResponse(url="/agent/tickets")
        return RedirectResponse(url="/portal/")
    return RedirectResponse(url="/login")
