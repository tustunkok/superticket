"""Core state machine logic for ticket lifecycle management."""

from superticket.core.exceptions import InvalidStateTransition
from superticket.models.enums import TicketState

# Mapping of each state to the set of states it may legally transition into.
VALID_TRANSITIONS: dict[TicketState, set[TicketState]] = {
    TicketState.NEW: {
        TicketState.TRIAGE,
        TicketState.ASSIGNED,
    },
    TicketState.TRIAGE: {
        TicketState.ASSIGNED,
    },
    TicketState.ASSIGNED: {
        TicketState.IN_PROGRESS,
        TicketState.PENDING_VENDOR,
    },
    TicketState.IN_PROGRESS: {
        TicketState.PENDING_VENDOR,
        TicketState.RESOLVED,
    },
    TicketState.PENDING_VENDOR: {
        TicketState.IN_PROGRESS,
        TicketState.RESOLVED,
    },
    TicketState.RESOLVED: {
        TicketState.CLOSED,
        TicketState.IN_PROGRESS,  # Re-opening (within or outside the 48h window)
    },
    TicketState.CLOSED: set(),  # Terminal state — no further transitions
}


def transition(current: TicketState, target: TicketState) -> TicketState:
    """Attempt to move a ticket from *current* to *target*.

    Args:
        current: The present state of the ticket.
        target: The desired next state.

    Returns:
        The target state when the transition is valid.

    Raises:
        InvalidStateTransition: If the move is not allowed.
    """
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise InvalidStateTransition(current.value, target.value)
    return target
