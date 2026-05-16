"""Web view routes for SuperTicket."""

from superticket.views.admin import router as admin_router
from superticket.views.auth import router as auth_router
from superticket.views.portal import router as portal_router
from superticket.views.agent import router as agent_router
from superticket.views.kb import router as kb_router

__all__ = ["auth_router", "portal_router", "agent_router", "kb_router", "admin_router"]
