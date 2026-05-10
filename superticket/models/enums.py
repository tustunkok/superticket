"""Domain enums for SuperTicket."""

from enum import Enum


class TicketState(str, Enum):
    """Lifecycle states of a ticket."""

    NEW = "new"
    TRIAGE = "triage"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_VENDOR = "pending_vendor"
    RESOLVED = "resolved"
    CLOSED = "closed"
