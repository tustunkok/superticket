"""Tests for SQLAlchemy ORM models."""

from datetime import datetime

import pytest
from sqlalchemy import select

from superticket.models.enums import TicketState
from superticket.models.ticket import AuditLog, Ticket


class TestTicketModel:
    """CRUD and property assertions for Ticket."""

    def test_create_ticket(self, db_session):
        """A ticket can be created with minimum required fields."""
        ticket = Ticket(
            id="INC-2026-001",
            requester_id="user-42",
            category="Hardware",
            sub_category="Laptop",
            item="Screen",
            urgency="high",
            impact="individual",
            priority="P2",
        )
        db_session.add(ticket)
        db_session.commit()

        result = db_session.execute(select(Ticket).where(Ticket.id == "INC-2026-001"))
        fetched = result.scalar_one()
        assert fetched.id == "INC-2026-001"
        assert fetched.requester_id == "user-42"
        assert fetched.state == TicketState.NEW.value
        assert isinstance(fetched.created_at, datetime)
        # Note: SQLite strips timezone info on round-trip.

    def test_default_state_is_new(self, db_session):
        """If state is omitted, it defaults to 'new'."""
        ticket = Ticket(
            id="INC-2026-002",
            requester_id="user-99",
            category="Software",
            sub_category="Bug",
            item="Login",
            urgency="low",
            impact="dept",
            priority="P3",
        )
        db_session.add(ticket)
        db_session.commit()

        result = db_session.execute(select(Ticket).where(Ticket.id == "INC-2026-002"))
        fetched = result.scalar_one()
        assert fetched.state == TicketState.NEW.value

    def test_ticket_repr(self, db_session):
        """__repr__ returns a helpful string."""
        ticket = Ticket(
            id="INC-2026-003",
            requester_id="user-1",
            category="Network",
            sub_category="VPN",
            item="Connection",
            urgency="medium",
            impact="org",
            priority="P1",
            state=TicketState.ASSIGNED.value,
        )
        db_session.add(ticket)
        db_session.commit()

        assert "INC-2026-003" in repr(ticket)
        assert "assigned" in repr(ticket)

    def test_delete_ticket_cascades_to_audit_logs(self, db_session):
        """Removing a ticket deletes its related audit logs."""
        ticket = Ticket(
            id="INC-2026-004",
            requester_id="user-7",
            category="Access",
            sub_category="Account",
            item="Unlock",
            urgency="high",
            impact="individual",
            priority="P2",
        )
        db_session.add(ticket)
        db_session.flush()

        log = AuditLog(
            ticket_id=ticket.id,
            action="state_change",
            new_value={"state": TicketState.ASSIGNED.value},
        )
        db_session.add(log)
        db_session.commit()

        db_session.delete(ticket)
        db_session.commit()

        result = db_session.execute(select(AuditLog).where(AuditLog.ticket_id == "INC-2026-004"))
        assert result.scalar() is None


class TestAuditLogModel:
    """CRUD and property assertions for AuditLog."""

    def test_create_audit_log(self, db_session):
        """An audit log can be linked to a ticket."""
        ticket = Ticket(
            id="INC-2026-005",
            requester_id="user-3",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            priority="P4",
        )
        db_session.add(ticket)
        db_session.flush()

        log = AuditLog(
            ticket_id=ticket.id,
            action="created",
            old_value=None,
            new_value={"id": "INC-2026-005", "state": "new"},
            performed_by="system",
        )
        db_session.add(log)
        db_session.commit()

        result = db_session.execute(select(AuditLog).where(AuditLog.ticket_id == "INC-2026-005"))
        fetched = result.scalar_one()
        assert fetched.action == "created"
        assert fetched.new_value == {"id": "INC-2026-005", "state": "new"}
        assert fetched.performed_by == "system"
        assert isinstance(fetched.timestamp, datetime)
        # Note: SQLite strips timezone info on round-trip.

    def test_audit_log_repr(self, db_session):
        """__repr__ returns a helpful string."""
        ticket = Ticket(
            id="INC-2026-006",
            requester_id="user-5",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            priority="P4",
        )
        db_session.add(ticket)
        db_session.flush()

        log = AuditLog(
            ticket_id=ticket.id,
            action="updated",
            new_value={"priority": "P1"},
        )
        db_session.add(log)
        db_session.commit()

        assert "updated" in repr(log)

    def test_ticket_audit_log_relationship(self, db_session):
        """Ticket.audit_logs yields the linked audit log rows."""
        ticket = Ticket(
            id="INC-2026-007",
            requester_id="user-8",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            priority="P4",
        )
        db_session.add(ticket)
        db_session.flush()

        for action in ("created", "assigned"):
            db_session.add(
                AuditLog(
                    ticket_id=ticket.id,
                    action=action,
                    new_value={"state": action},
                )
            )
        db_session.commit()

        ticket_fresh = db_session.execute(
            select(Ticket).where(Ticket.id == "INC-2026-007")
        ).scalar_one()
        assert len(ticket_fresh.audit_logs) == 2
        assert {log.action for log in ticket_fresh.audit_logs} == {"created", "assigned"}
