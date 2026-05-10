"""Domain exceptions for SuperTicket."""


class InvalidStateTransition(Exception):
    """Raised when a forbidden ticket state transition is attempted."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition from '{current}' to '{target}'.")
        self.current = current
        self.target = target
