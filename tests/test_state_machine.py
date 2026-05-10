"""Tests for the ticket state machine."""

import pytest

from superticket.core.exceptions import InvalidStateTransition
from superticket.models.enums import TicketState
from superticket.services.state_machine import VALID_TRANSITIONS, transition


class TestValidTransitions:
    """Happy-path transitions."""

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (TicketState.NEW, TicketState.TRIAGE),
            (TicketState.NEW, TicketState.ASSIGNED),
            (TicketState.TRIAGE, TicketState.ASSIGNED),
            (TicketState.ASSIGNED, TicketState.IN_PROGRESS),
            (TicketState.ASSIGNED, TicketState.PENDING_VENDOR),
            (TicketState.IN_PROGRESS, TicketState.PENDING_VENDOR),
            (TicketState.IN_PROGRESS, TicketState.RESOLVED),
            (TicketState.PENDING_VENDOR, TicketState.IN_PROGRESS),
            (TicketState.PENDING_VENDOR, TicketState.RESOLVED),
            (TicketState.RESOLVED, TicketState.CLOSED),
            (TicketState.RESOLVED, TicketState.IN_PROGRESS),
        ],
    )
    def test_allowed_transition(self, current: TicketState, target: TicketState) -> None:
        """transition() should return the target state for every allowed move."""
        result = transition(current, target)
        assert result is target


class TestInvalidTransitions:
    """Forbidden transitions."""

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            # Cannot skip RESOLVED before CLOSED
            (TicketState.NEW, TicketState.CLOSED),
            (TicketState.TRIAGE, TicketState.CLOSED),
            (TicketState.ASSIGNED, TicketState.CLOSED),
            (TicketState.IN_PROGRESS, TicketState.CLOSED),
            (TicketState.PENDING_VENDOR, TicketState.CLOSED),
            # No backward jumps
            (TicketState.ASSIGNED, TicketState.NEW),
            (TicketState.ASSIGNED, TicketState.TRIAGE),
            (TicketState.IN_PROGRESS, TicketState.ASSIGNED),
            (TicketState.IN_PROGRESS, TicketState.TRIAGE),
            (TicketState.IN_PROGRESS, TicketState.NEW),
            (TicketState.RESOLVED, TicketState.ASSIGNED),
            (TicketState.RESOLVED, TicketState.TRIAGE),
            (TicketState.RESOLVED, TicketState.NEW),
            (TicketState.CLOSED, TicketState.RESOLVED),
            (TicketState.CLOSED, TicketState.IN_PROGRESS),
            (TicketState.CLOSED, TicketState.NEW),
            # Self-loops are not allowed
            (TicketState.NEW, TicketState.NEW),
            (TicketState.ASSIGNED, TicketState.ASSIGNED),
            (TicketState.RESOLVED, TicketState.RESOLVED),
            (TicketState.CLOSED, TicketState.CLOSED),
        ],
    )
    def test_disallowed_transition_raises(self, current: TicketState, target: TicketState) -> None:
        """transition() should raise InvalidStateTransition for forbidden moves."""
        with pytest.raises(InvalidStateTransition) as exc_info:
            transition(current, target)

        err = exc_info.value
        assert err.current == current.value
        assert err.target == target.value
        assert current.value in str(err)
        assert target.value in str(err)


class TestTransitionMapCompleteness:
    """Ensure every TicketState has an entry in VALID_TRANSITIONS."""

    def test_all_states_present(self) -> None:
        assert set(VALID_TRANSITIONS.keys()) == set(TicketState)

    def test_closed_is_terminal(self) -> None:
        """CLOSED must not allow any outward transitions."""
        assert VALID_TRANSITIONS[TicketState.CLOSED] == set()

    def test_no_self_loops_by_default(self) -> None:
        for state, targets in VALID_TRANSITIONS.items():
            assert state not in targets
