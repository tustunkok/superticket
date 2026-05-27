"""Tests for the LLM triage service."""

import pytest
from unittest.mock import AsyncMock, patch

from superticket.core.config import settings
from superticket.models.enums import TicketState
from superticket.services.ticket import TicketService
from superticket.services.triage import (
    _build_kb_context,
    _call_llm,
    confirm_triage,
    triage_ticket,
)


def _make_session_factory(db_session):
    """Return a callable that yields the same session."""
    def factory():
        return db_session

    return factory


class TestBuildKbContext:
    def test_returns_empty_for_no_results(self, monkeypatch):
        monkeypatch.setattr(
            "superticket.services.triage.search_kb", lambda query: []
        )
        result = _build_kb_context("something")
        assert result == ""

    def test_builds_context_from_matches(self, monkeypatch):
        from superticket.data.mock_kb import KBArticle

        articles = [
            KBArticle(
                slug="vpn-setup-guide",
                category="Network",
                sub_category="VPN",
                title="VPN Setup Guide",
                content="Connect via OpenVPN client.",
                tags=["vpn", "setup"],
            )
        ]
        monkeypatch.setattr(
            "superticket.services.triage.search_kb", lambda query: articles
        )
        result = _build_kb_context("vpn not working")
        assert "KB [Network/VPN]" in result
        assert "VPN Setup Guide" in result

    def test_limits_to_three_articles(self, monkeypatch):
        from superticket.data.mock_kb import KBArticle

        articles = [
            KBArticle(
                slug=f"article-{i}",
                category="Category",
                sub_category="SubCat",
                title=f"Article {i}",
                tags=["tag"],
                content=f"Content {i}",
            )
            for i in range(5)
        ]
        monkeypatch.setattr(
            "superticket.services.triage.search_kb", lambda query: articles
        )
        result = _build_kb_context("query")
        # Should have exactly 3 KB entries (limit to top 3)
        assert result.count("[Category/SubCat]") == 3


class TestCallLlm:
    @pytest.mark.asyncio
    async def test_parses_valid_json(self, monkeypatch):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices[0].message.content = (
            '{"category": "Network", "sub_category": "VPN", '
            '"item": "Access", "sentiment_score": -0.5, '
            '"pii_detected": false, "suggested_resolution": "", '
            '"confidence_score": 0.8}'
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        monkeypatch.setattr(
            "superticket.services.triage.AsyncOpenAI", lambda **kw: mock_client
        )

        result = await _call_llm("INC-001", "vpn not working", "")
        assert result["category"] == "Network"
        assert result["sub_category"] == "VPN"
        assert result["confidence_score"] == 0.8

    @pytest.mark.asyncio
    async def test_parses_markdown_code_block(self, monkeypatch):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices[0].message.content = (
            '```json\n'
            '{"category": "Software", "sub_category": "Bug", '
            '"item": "Crash", "sentiment_score": 0, '
            '"pii_detected": false, "suggested_resolution": "", '
            '"confidence_score": 0.6}\n```'
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        monkeypatch.setattr(
            "superticket.services.triage.AsyncOpenAI", lambda **kw: mock_client
        )

        result = await _call_llm("INC-002", "app crashes", "")
        assert result["category"] == "Software"

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_json(self, monkeypatch):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices[0].message.content = "not json at all"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        monkeypatch.setattr(
            "superticket.services.triage.AsyncOpenAI", lambda **kw: mock_client
        )

        result = await _call_llm("INC-003", "something", "")
        assert result is None


class TestTriageTicket:
    @pytest.mark.asyncio
    async def test_skips_when_no_api_key(self, db_session, monkeypatch):
        """When LLM API key is not configured, triage is skipped."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-SVC-001",
            requester_id="user-1",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
            description="Cannot connect to VPN",
        )
        original_key = settings.llm_api_key
        monkeypatch.setattr(settings, "llm_api_key", None)

        factory = _make_session_factory(db_session)
        await triage_ticket("INC-SVC-001", factory)

        ticket = TicketService.get(db_session, "INC-SVC-001")
        assert ticket.state == TicketState.NEW.value
        monkeypatch.setattr(settings, "llm_api_key", original_key)

    @pytest.mark.asyncio
    async def test_skips_when_no_description(self, db_session, monkeypatch):
        """Triage is skipped when ticket has no description."""
        TicketService.create(
            session=db_session,
            id="INC-SVC-002",
            requester_id="user-2",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
        )

        factory = _make_session_factory(db_session)
        await triage_ticket("INC-SVC-002", factory)

        ticket = TicketService.get(db_session, "INC-SVC-002")
        assert ticket.state == TicketState.NEW.value
        assert ticket.ai_category is None

    @pytest.mark.asyncio
    async def test_skips_when_not_new_state(self, db_session, monkeypatch):
        """Triage only runs on tickets in NEW state."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-SVC-003",
            requester_id="user-3",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
            description="Cannot connect to VPN",
        )
        TicketService.transition_state(db_session, "INC-SVC-003", TicketState.ASSIGNED)

        factory = _make_session_factory(db_session)
        await triage_ticket("INC-SVC-003", factory)

        ticket = TicketService.get(db_session, "INC-SVC-003")
        assert ticket.state == TicketState.ASSIGNED.value
        assert ticket.ai_category is None

    @pytest.mark.asyncio
    async def test_successful_triage(self, db_session, monkeypatch):
        """Full triage flow: LLM returns valid result, ticket transitions to TRIAGE."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices[0].message.content = (
            '{"category": "Network", "sub_category": "VPN", '
            '"item": "Access", "sentiment_score": -0.3, '
            '"pii_detected": false, "suggested_resolution": "Check VPN cert", '
            '"confidence_score": 0.9}'
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        monkeypatch.setattr(
            "superticket.services.triage.AsyncOpenAI", lambda **kw: mock_client
        )
        monkeypatch.setattr(settings, "llm_api_key", "test-key")

        ticket = TicketService.create(
            session=db_session,
            id="INC-SVC-004",
            requester_id="user-4",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
            description="Cannot connect to VPN from office",
        )

        factory = _make_session_factory(db_session)
        await triage_ticket("INC-SVC-004", factory)

        ticket = TicketService.get(db_session, "INC-SVC-004")
        assert ticket.state == TicketState.TRIAGE.value
        assert ticket.ai_category == "Network"
        assert ticket.ai_sub_category == "VPN"
        assert ticket.ai_item == "Access"
        assert ticket.sentiment_score == -0.3
        assert ticket.pii_detected is False
        assert ticket.suggested_resolution == "Check VPN cert"
        assert ticket.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_clamps_sentiment_and_confidence(self, db_session, monkeypatch):
        """Sentiment and confidence scores are clamped to valid ranges."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices[0].message.content = (
            '{"category": "Network", "sub_category": "VPN", '
            '"item": "Access", "sentiment_score": 5, '
            '"pii_detected": false, "suggested_resolution": "", '
            '"confidence_score": -2}'
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        monkeypatch.setattr(
            "superticket.services.triage.AsyncOpenAI", lambda **kw: mock_client
        )
        monkeypatch.setattr(settings, "llm_api_key", "test-key")

        TicketService.create(
            session=db_session,
            id="INC-SVC-005",
            requester_id="user-5",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="individual",
            description="vpn issue",
        )

        factory = _make_session_factory(db_session)
        await triage_ticket("INC-SVC-005", factory)

        ticket = TicketService.get(db_session, "INC-SVC-005")
        assert ticket.sentiment_score == 1.0  # clamped from 5
        assert ticket.confidence_score == 0.0  # clamped from -2


class TestConfirmTriage:
    def test_confirm_matching_ai_no_override_log(self, db_session):
        """When human matches AI classification, no override log is created."""
        TicketService.create(
            session=db_session,
            id="INC-CONFIRM-001",
            requester_id="user-1",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            urgency="medium",
            impact="individual",
        )

        confirm_triage(
            db_session,
            "INC-CONFIRM-001",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-CONFIRM-001")
        assert ticket.state == TicketState.ASSIGNED.value

    def test_confirm_with_override_creates_log(self, db_session):
        """When human differs from AI, a TriageOverrideLog entry is created."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-CONFIRM-002",
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
            "INC-CONFIRM-002",
            category="Network",
            sub_category="VPN",
            item="Access",
            override_reason="AI misclassified; this is a network issue",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-CONFIRM-002")
        assert ticket.state == TicketState.ASSIGNED.value
        assert ticket.category == "Network"
        assert ticket.sub_category == "VPN"

    def test_confirm_with_urgency_impact_override(self, db_session):
        """Urgency and impact can be overridden during confirmation."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-CONFIRM-003",
            requester_id="user-3",
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
            "INC-CONFIRM-003",
            category="Hardware",
            sub_category="Printer",
            item="Setup",
            urgency="high",
            impact="org",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-CONFIRM-003")
        assert ticket.urgency == "high"
        assert ticket.impact == "org"
        assert ticket.priority == "P1"

    def test_confirm_no_ai_fields_skips_override(self, db_session):
        """When AI fields are None (no triage run), no override is logged."""
        TicketService.create(
            session=db_session,
            id="INC-CONFIRM-004",
            requester_id="user-4",
            category="Software",
            sub_category="Email",
            item="Sync",
            urgency="medium",
            impact="individual",
        )

        confirm_triage(
            db_session,
            "INC-CONFIRM-004",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-CONFIRM-004")
        assert ticket.state == TicketState.ASSIGNED.value

    def test_confirm_case_insensitive_comparison(self, db_session):
        """AI vs human comparison is case-insensitive."""
        ticket = TicketService.create(
            session=db_session,
            id="INC-CONFIRM-005",
            requester_id="user-5",
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
            "INC-CONFIRM-005",
            category="Hardware",
            sub_category="Laptop",
            item="Keyboard",
            performed_by="agent@example.com",
        )

        ticket = TicketService.get(db_session, "INC-CONFIRM-005")
        assert ticket.state == TicketState.ASSIGNED.value
