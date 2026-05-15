"""FastAPI application factory & lifespan events."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from superticket.api.v1.auth import router as auth_router
from superticket.api.v1.tickets import router as tickets_router
from superticket.core.config import settings
from superticket.core.exceptions import InvalidStateTransition, TicketNotFound
from superticket.db.engine import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (MVP shortcut; Alembic in production)."""
    init_db()
    yield


app = FastAPI(
    title="SuperTicket",
    description="High-Velocity Ticketing & Hybrid AI Triage",
    version=settings.app_version,
    lifespan=lifespan,
)


@app.exception_handler(TicketNotFound)
async def ticket_not_found_handler(request, exc: TicketNotFound):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "code": "TICKET_NOT_FOUND"},
    )


@app.exception_handler(InvalidStateTransition)
async def invalid_state_transition_handler(request, exc: InvalidStateTransition):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "code": "INVALID_STATE_TRANSITION"},
    )


app.include_router(tickets_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}
