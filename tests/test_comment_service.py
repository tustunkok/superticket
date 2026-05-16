"""Tests for CommentService business logic."""

import uuid

import pytest

from superticket.core.exceptions import TicketNotFound
from superticket.services.comment import CommentService
from superticket.services.ticket import TicketService


class TestCreateComment:
    def test_create_comment_on_ticket(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C01",
            requester_id="user-c01",
            category="Hardware",
            sub_category="Laptop",
            item="Screen",
            urgency="high",
            impact="individual",
        )
        comment = CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C01",
            author_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            author_name="Test Author",
            content="This is a test comment",
        )
        assert comment.ticket_id == "INC-2026-C01"
        assert comment.author_name == "Test Author"
        assert comment.content == "This is a test comment"
        assert comment.is_internal is False

    def test_create_internal_comment(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C02",
            requester_id="user-c02",
            category="Software",
            sub_category="Bug",
            item="Crash",
            urgency="medium",
            impact="dept",
        )
        comment = CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C02",
            author_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            author_name="Agent",
            content="Internal note",
            is_internal=True,
        )
        assert comment.is_internal is True

    def test_create_comment_on_missing_ticket_raises(self, db_session):
        with pytest.raises(TicketNotFound) as exc_info:
            CommentService.create(
                session=db_session,
                ticket_id="INC-NOPE",
                author_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                author_name="Nobody",
                content="Should fail",
            )
        assert "INC-NOPE" in str(exc_info.value)


class TestListComments:
    def test_list_comments_for_ticket(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C03",
            requester_id="user-c03",
            category="Network",
            sub_category="VPN",
            item="Access",
            urgency="low",
            impact="org",
        )
        CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C03",
            author_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            author_name="Agent 1",
            content="First comment",
        )
        CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C03",
            author_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            author_name="Agent 2",
            content="Second comment",
            is_internal=True,
        )

        comments = CommentService.list_for_ticket(db_session, "INC-2026-C03")
        assert len(comments) == 2
        contents = {c.content for c in comments}
        assert contents == {"First comment", "Second comment"}

    def test_list_comments_exclude_internal(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C04",
            requester_id="user-c04",
            category="Access",
            sub_category="Account",
            item="Unlock",
            urgency="high",
            impact="individual",
        )
        CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C04",
            author_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            author_name="User",
            content="Public comment",
        )
        CommentService.create(
            session=db_session,
            ticket_id="INC-2026-C04",
            author_id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            author_name="Agent",
            content="Internal note",
            is_internal=True,
        )

        comments = CommentService.list_for_ticket(
            db_session, "INC-2026-C04", include_internal=False
        )
        assert len(comments) == 1
        assert comments[0].content == "Public comment"

    def test_list_comments_empty(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C05",
            requester_id="user-c05",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
        )
        comments = CommentService.list_for_ticket(db_session, "INC-2026-C05")
        assert len(comments) == 0

    def test_list_comments_pagination(self, db_session):
        TicketService.create(
            session=db_session,
            id="INC-2026-C06",
            requester_id="user-c06",
            category="Misc",
            sub_category="Other",
            item="General",
            urgency="low",
            impact="individual",
        )
        for i in range(5):
            CommentService.create(
                session=db_session,
                ticket_id="INC-2026-C06",
                author_id=uuid.UUID(f"00000000-0000-0000-0000-00000000000{i}"),
                author_name=f"Author {i}",
                content=f"Comment {i}",
            )

        comments = CommentService.list_for_ticket(db_session, "INC-2026-C06", skip=0, limit=3)
        assert len(comments) == 3

        comments = CommentService.list_for_ticket(db_session, "INC-2026-C06", skip=3, limit=10)
        assert len(comments) == 2
