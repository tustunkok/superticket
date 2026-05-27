"""Tests for TriageOverrideLog model and confirm_triage service."""

import pytest
from sqlalchemy import select

from superticket.models.enums import TicketState
from superticket.models.triage_log import TriageOverrideLog
from superticket.services.ticket import TicketService
from superticket.services.triage import confirm_triage


class TestConfirmTriage:
    def test_confirm_with_matching_ai(self, db_session):
        """When human matches AI, no override log is created."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-001",
            requester_id="user-1",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            urgency="medium",
            impact="individual",
        )
        ticket.ai_category = "Hardware"
        ticket.ai_sub_category = "Laptop"
        ticket.ai_item = "Keyboard"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-001",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-TRIAGE-001")
        assert ticket.state == TicketState.ASSIGNED.value
        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 0

    def test_confirm_with_override_creates_log(self, db_session):
        """When human differs from AI, an override log is created."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-002",
            requester_id="user-2",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
        )
        ticket.ai_category = "Software"
        ticket.ai_sub_category = "Bug"
        ticket.ai_item = "Crash"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-002",
            category="Network",
            sub_category="VPN",
            item="Access",
            override_reason="AI misclassified; this is a network issue",
            performed_by="agent@example.com",
        )

        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 1
        log = logs[0]
        assert log.ticket_id == "INC-TRIAGE-002"
        assert log.ai_category == "Software"
        assert log.human_category == "Network"
        assert log.ai_sub_category == "Bug"
        assert log.human_sub_category == "VPN"
        assert log.override_reason == "AI misclassified; this is a network issue"
        assert log.performed_by == "agent@example.com"

    def test_confirm_without_explicit_values_uses_ticket(self, db_session):
        """When no human values provided, uses existing ticket fields."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-003",
            requester_id="user-3",
            category="Access",
            sub_category="Account",
            item="Unlock",
            urgency="high",
            impact="individual",
        )
        ticket.ai_category = "Access"
        ticket.ai_sub_category = "Account"
        ticket.ai_item = "Password Reset"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-003",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-TRIAGE-003")
        assert ticket.category == "Access"
        assert ticket.sub_category == "Account"
        assert ticket.item == "Unlock"
        assert ticket.state == TicketState.ASSIGNED.value

        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 1
        log = logs[0]
        assert log.ai_item == "Password Reset"
        assert log.human_item == "Unlock"

    def test_confirm_with_urgency_impact_override(self, db_session):
        """Urgency and impact can be overridden in confirm_triage."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-004",
            requester_id="user-4",
            category="Hardware",
            sub_category="Printer",
            item="Setup",
            urgency="low",
            impact="individual",
        )
        ticket.ai_category = "Hardware"
        ticket.ai_sub_category = "Printer"
        ticket.ai_item = "Setup"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-004",
            category="Hardware",
            sub_category="Printer",
            item="Setup",
            urgency="high",
            impact="org",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-TRIAGE-004")
        assert ticket.urgency == "high"
        assert ticket.impact == "org"
        assert ticket.priority == "P1"
        assert ticket.state == TicketState.ASSIGNED.value

    def test_confirm_partial_override(self, db_session):
        """Only overriding sub_category while matching on others."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-005",
            requester_id="user-5",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="medium",
            impact="individual",
        )
        ticket.ai_category = "Network"
        ticket.ai_sub_category = "Wi-Fi"
        ticket.ai_item = "Connectivity"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-005",
            category="Network",
            sub_category="VPN",
            item="Access",
            performed_by="agent@example.com",
        )

        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 1
        log = logs[0]
        assert log.ai_sub_category == "Wi-Fi"
        assert log.human_sub_category == "VPN"

    def test_confirm_no_ai_fields_skips_override(self, db_session):
        """When AI fields are None (no triage run), no override is logged."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-006",
            requester_id="user-6",
            category="Software",
            sub_category="Email",
            item="Sync",
            urgency="medium",
            impact="individual",
        )

        confirm_triage(
            db_session,
            "INC-TRIAGE-006",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-TRIAGE-006")
        assert ticket.state == TicketState.ASSIGNED.value

        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 0

    def test_confirm_case_insensitive_comparison(self, db_session):
        """AI vs human comparison is case-insensitive."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-TRIAGE-007",
            requester_id="user-7",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            urgency="low",
            impact="individual",
        )
        ticket.ai_category = "hardware"
        ticket.ai_sub_category = "laptop"
        ticket.ai_item = "keyboard"
        db_session.add(ticket)

        confirm_triage(
            db_session,
            "INC-TRIAGE-007",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            performed_by="agent@example.com",
        )

        logs = db_session.execute(
            select(TriageOverrideLog)
        ).scalars().all()
        assert len(logs) == 0
