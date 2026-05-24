"""Tests for the TicketService business logic layer."""

import pytest
from sqlalchemy import select

from superticket.core.exceptions import InvalidStateTransition, TicketNotFound
from superticket.models.enums import TicketState
from superticket.models.ticket import AuditLog
from superticket.services.ticket import TicketService


class TestCreate:
    def test_create_ticket_defaults_to_new(self, db_session):
        ticket = TicketService.create(
            session=db_session,
            id="INC-2026-010",
            requester_id="user-10",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            urgency="medium",
            impact="individual",
        )
        assert ticket.id == "INC-2026-010"
        assert ticket.state == TicketState.NEW.value

    def test_create_generates_audit_log(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-011",
            requester_id="user-11",
            category="Software",
            sub_category="Bug",
            item="Crash",
            urgency="high",
            impact="dept",
        )
        logs = db_session.execute(
            select(AuditLog).where(AuditLog.ticket_id == "INC-2026-011")
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "created"
        assert logs[0].new_value["state"] == TicketState.NEW.value

    def test_create_ticket_with_description(self, db_session):
        ticket = TicketService.create(
            session=db_session,
            id="INC-2026-050",
            requester_id="user-50",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            urgency="medium",
            impact="individual",
            description="The keyboard keys are sticking",
        )
        assert ticket.description == "The keyboard keys are sticking"

    def test_create_ticket_without_description(self, db_session):
        ticket = TicketService.create(
            session=db_session,
            id="INC-2026-051",
            requester_id="user-51",
            category="Hardware",
            sub_category="Laptop",
            item="Screen",
            urgency="high",
            impact="individual",
        )
        assert ticket.description is None

    def test_create_audit_log_includes_description(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-052",
            requester_id="user-52",
            category="Software",
            sub_category="Bug",
            item="Crash",
            urgency="high",
            impact="dept",
            description="Application crashes on startup",
        )
        logs = db_session.execute(
            select(AuditLog).where(AuditLog.ticket_id == "INC-2026-052")
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].new_value["description"] == "Application crashes on startup"


class TestGet:
    def test_get_existing_ticket(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-012",
            requester_id="user-12",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="org",
        )
        fetched = TicketService.get(db_session, "INC-2026-012")
        assert fetched.requester_id == "user-12"

    def test_get_missing_raises(self, db_session):
        with pytest.raises(TicketNotFound) as exc_info:
            TicketService.get(db_session, "INC-NOPE")
        assert "INC-NOPE" in str(exc_info.value)


class TestList:
    def test_list_pagination(self, db_session):
        for i in range(5):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{100 + i}",
                requester_id=f"user-{i}",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        results = TicketService.list_(db_session, skip=0, limit=3)
        assert len(results) == 3
        # Newest first
        assert results[0].id == "INC-2026-104"

    def test_list_skip(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{200 + i}",
                requester_id=f"user-{i}",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        results = TicketService.list_(db_session, skip=1, limit=10)
        assert len(results) == 2
        assert results[0].id == "INC-2026-201"

    def test_list_filter_by_requester_id(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{300 + i}",
                requester_id=f"user-{i}",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        results = TicketService.list_(db_session, requester_id="user-1")
        assert len(results) == 1
        assert results[0].id == "INC-2026-301"

    def test_list_filter_by_state(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{400 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.transition_state(db_session, "INC-2026-401", TicketState.TRIAGE)
        results = TicketService.list_(db_session, state=TicketState.NEW.value)
        assert len(results) == 2
        for r in results:
            assert r.state == TicketState.NEW.value

    def test_list_filter_by_priority(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{500 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.update(db_session, "INC-2026-501", priority="P1")
        results = TicketService.list_(db_session, priority="P4")
        assert len(results) == 2

    def test_list_combined_filters_with_pagination(self, db_session):
        for i in range(5):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{600 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.transition_state(db_session, "INC-2026-604", TicketState.TRIAGE)
        TicketService.transition_state(db_session, "INC-2026-603", TicketState.TRIAGE)
        results = TicketService.list_(db_session, state=TicketState.NEW.value, skip=1, limit=1)
        assert len(results) == 1
        assert results[0].state == TicketState.NEW.value

    def test_list_no_filter(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{700 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        results = TicketService.list_(db_session)
        assert len(results) >= 3


class TestCount:
    def test_count_unfiltered(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{800 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        assert TicketService.count(db_session) >= 3

    def test_count_filtered_by_state(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{900 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.transition_state(db_session, "INC-2026-901", TicketState.TRIAGE)
        assert TicketService.count(db_session, state=TicketState.NEW.value) == 2

    def test_count_filtered_by_priority(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{910 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.update(db_session, "INC-2026-911", priority="P1")
        assert TicketService.count(db_session, priority="P4") == 2

    def test_count_filtered_by_requester_id(self, db_session):
        for i in range(3):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{920 + i}",
                requester_id=f"user-{i}",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        assert TicketService.count(db_session, requester_id="user-1") == 1

    def test_count_combined_filters(self, db_session):
        for i in range(4):
            TicketService.create(
                session=db_session,
                id=f"INC-2026-{930 + i}",
                requester_id="user-common",
                category="Misc",
                sub_category="Other",
                item="General",
                urgency="low",
                impact="individual",
            )
        TicketService.transition_state(db_session, "INC-2026-933", TicketState.TRIAGE)
        TicketService.update(db_session, "INC-2026-931", priority="P1")
        assert (
            TicketService.count(
                db_session, state=TicketState.NEW.value, priority="P4"
            )
            == 2
        )



class TestUpdate:
    def test_update_allowed_fields(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-013",
            requester_id="user-13",
            category="Access",
            sub_category="Account",
            item="Unlock",
            urgency="high",
            impact="individual",

        )
        updated = TicketService.update(
            db_session,
            "INC-2026-013",
            performed_by="admin-1",
            category="Hardware",
            urgency="low",
        )
        assert updated.category == "Hardware"
        assert updated.urgency == "low"

    def test_update_audit_log(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-014",
            requester_id="user-14",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        TicketService.update(
            db_session,
            "INC-2026-014",
            performed_by="admin-2",
            priority="P1",
        )
        logs = db_session.execute(
            select(AuditLog)
            .where(AuditLog.ticket_id == "INC-2026-014")
            .where(AuditLog.action == "updated")
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].old_value == {"priority": "P4"}
        assert logs[0].new_value == {"priority": "P1"}
        assert logs[0].performed_by == "admin-2"

    def test_update_disallowed_field_raises(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-015",
            requester_id="user-15",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        with pytest.raises(ValueError, match="not mutable"):
            TicketService.update(db_session, "INC-2026-015", state="closed")

    def test_update_no_changes_does_not_create_audit(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-016",
            requester_id="user-16",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        TicketService.update(db_session, "INC-2026-016", category="Misc")
        logs = db_session.execute(
            select(AuditLog)
            .where(AuditLog.ticket_id == "INC-2026-016")
            .where(AuditLog.action == "updated")
        ).scalars().all()
        assert len(logs) == 0

    def test_update_description(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-053",
            requester_id="user-53",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            description="Initial description",
        )
        updated = TicketService.update(
            db_session,
            "INC-2026-053",
            performed_by="admin-3",
            description="Updated description",
        )
        assert updated.description == "Updated description"

    def test_update_description_audit_log(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-054",
            requester_id="user-54",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            description="Original description",
        )
        TicketService.update(
            db_session,
            "INC-2026-054",
            performed_by="admin-4",
            description="New description",
        )
        logs = db_session.execute(
            select(AuditLog)
            .where(AuditLog.ticket_id == "INC-2026-054")
            .where(AuditLog.action == "updated")
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].old_value == {"description": "Original description"}
        assert logs[0].new_value == {"description": "New description"}
        assert logs[0].performed_by == "admin-4"

    def test_update_description_to_none(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-055",
            requester_id="user-55",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
            description="Will be cleared",
        )
        updated = TicketService.update(
            db_session,
            "INC-2026-055",
            description=None,
        )
        assert updated.description is None


class TestTransitionState:
    def test_valid_transition(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-017",
            requester_id="user-17",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        updated = TicketService.transition_state(
            db_session, "INC-2026-017", TicketState.TRIAGE, performed_by="bot"
        )
        assert updated.state == TicketState.TRIAGE.value

    def test_invalid_transition_raises(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-018",
            requester_id="user-18",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        with pytest.raises(InvalidStateTransition):
            TicketService.transition_state(
                db_session, "INC-2026-018", TicketState.CLOSED
            )

    def test_transition_audit_log(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-019",
            requester_id="user-19",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        TicketService.transition_state(
            db_session, "INC-2026-019", TicketState.ASSIGNED, performed_by="dispatcher"
        )
        logs = db_session.execute(
            select(AuditLog)
            .where(AuditLog.ticket_id == "INC-2026-019")
            .where(AuditLog.action == "state_transition")
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].old_value == {"state": TicketState.NEW.value}
        assert logs[0].new_value == {"state": TicketState.ASSIGNED.value}
        assert logs[0].performed_by == "dispatcher"

    def test_terminal_state_no_further_transition(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-020",
            requester_id="user-20",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",

        )
        TicketService.transition_state(db_session, "INC-2026-020", TicketState.ASSIGNED)
        TicketService.transition_state(db_session, "INC-2026-020", TicketState.IN_PROGRESS)
        TicketService.transition_state(db_session, "INC-2026-020", TicketState.RESOLVED)
        TicketService.transition_state(db_session, "INC-2026-020", TicketState.CLOSED)

        with pytest.raises(InvalidStateTransition):
            TicketService.transition_state(
                db_session, "INC-2026-020", TicketState.IN_PROGRESS
            )
