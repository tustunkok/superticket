"""Domain exceptions for SuperTicket."""


class InvalidStateTransition(Exception):
    """Raised when a forbidden ticket state transition is attempted."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition from '{current}' to '{target}'.")
        self.current = current
        self.target = target


class TicketNotFound(Exception):
    """Raised when a requested ticket ID does not exist."""

    def __init__(self, ticket_id: str) -> None:
        super().__init__(f"Ticket '{ticket_id}' not found.")
        self.ticket_id = ticket_id


class InvalidCredentials(Exception):
    """Raised when authentication fails."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class TicketClosed(Exception):
    """Raised when attempting to comment on a closed ticket."""

    def __init__(self, ticket_id: str) -> None:
        super().__init__(f"Ticket '{ticket_id}' is closed. No further comments allowed.")
        self.ticket_id = ticket_id
