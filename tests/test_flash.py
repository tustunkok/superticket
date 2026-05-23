"""Tests for flash message utilities and integration with web routes."""

import pytest

from superticket.core.flash import set_flash, get_flashed_messages


class MockRequest:
    """Minimal mock of a Starlette request with session support."""

    def __init__(self):
        self.session = {}


class TestSetFlash:
    """Tests for the set_flash utility function."""

    def test_sets_info_category_by_default(self):
        request = MockRequest()
        set_flash(request, "Test message")
        assert request.session["flash"] == [("info", "Test message")]

    def test_sets_explicit_category(self):
        request = MockRequest()
        set_flash(request, "Success!", category="success")
        assert request.session["flash"] == [("success", "Success!")]

    def test_accumulates_multiple_messages(self):
        request = MockRequest()
        set_flash(request, "First")
        set_flash(request, "Second", category="error")
        assert len(request.session["flash"]) == 2
        assert request.session["flash"][0] == ("info", "First")
        assert request.session["flash"][1] == ("error", "Second")

    def test_raises_for_invalid_category(self):
        request = MockRequest()
        with pytest.raises(ValueError, match="Invalid flash category"):
            set_flash(request, "Bad", category="invalid")

    def test_resets_non_list_value(self):
        """If the flash key exists but is not a list, it should be reset."""
        request = MockRequest()
        request.session["flash"] = "corrupt"
        set_flash(request, "New message")
        assert isinstance(request.session["flash"], list)
        assert request.session["flash"] == [("info", "New message")]


class TestGetFlashedMessages:
    """Tests for the get_flashed_messages utility function."""

    def test_returns_empty_when_no_flash(self):
        request = MockRequest()
        result = get_flashed_messages(request)
        assert result == []

    def test_returns_and_consumes_messages(self):
        request = MockRequest()
        set_flash(request, "Hello", category="success")
        result = get_flashed_messages(request)
        assert result == [("success", "Hello")]
        # Second call should be empty (consumed)
        assert get_flashed_messages(request) == []

    def test_session_key_removed_after_read(self):
        request = MockRequest()
        set_flash(request, "Test")
        assert "flash" in request.session
        get_flashed_messages(request)
        assert "flash" not in request.session

    def test_returns_multiple_messages_preserving_order(self):
        request = MockRequest()
        set_flash(request, "First", category="info")
        set_flash(request, "Second", category="warning")
        set_flash(request, "Third", category="error")
        result = get_flashed_messages(request)
        assert len(result) == 3
        assert result[0] == ("info", "First")
        assert result[1] == ("warning", "Second")
        assert result[2] == ("error", "Third")

    def test_handles_corrupt_session_data(self):
        """Non-list flash data should be treated as empty."""
        request = MockRequest()
        request.session["flash"] = "corrupt"
        result = get_flashed_messages(request)
        assert result == []


class TestFlashIntegration:
    """Integration tests using FastAPI TestClient to verify redirect behavior."""

    @pytest.fixture(scope="module")
    def client(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool
        from sqlalchemy.orm import sessionmaker

        from superticket.db.base import Base
        from superticket.main import app
        from superticket.models import ticket, user, comment  # noqa: F401

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        from superticket.core.dependencies import get_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            yield c

        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

    def test_login_failure_sets_flash_error(self, client):
        """Login with wrong credentials should redirect with flash error."""
        # Register a user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "flash_test@example.com",
                "password": "password123",
                "full_name": "Flash Test User",
            },
        )
        # Login with wrong password — should redirect to /login with flash error
        resp = client.post(
            "/login",
            data={"email": "flash_test@example.com", "password": "wrong"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_register_success_sets_flash_message(self, client):
        """Successful registration should redirect with flash success."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "flash_reg@example.com",
                "password": "password123",
                "full_name": "Flash Reg User",
            },
        )
        assert resp.status_code == 201

    def test_ticket_creation_sets_flash_success(self, client):
        """Creating a ticket should redirect with flash success message."""
        # Register and login as portal user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "flash_portal@example.com",
                "password": "password123",
                "full_name": "Flash Portal User",
            },
        )
        client.post(
            "/login",
            data={"email": "flash_portal@example.com", "password": "password123"},
        )
        # Create ticket — should redirect with flash success
        resp = client.post(
            "/portal/tickets",
            data={
                "category": "hardware",
                "sub_category": "laptop",
                "item": "my laptop",
                "urgency": "medium",
                "impact": "individual",
                "description": "Testing flash messages",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_closed_ticket_comment_sets_flash_warning(self, client):
        """Attempting to comment on a closed ticket should set flash warning."""
        # Register agent and portal user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "flash_agent@example.com",
                "password": "password123",
                "full_name": "Flash Agent User",
            },
        )

        # Login as agent to create and close a ticket
        client.post(
            "/login",
            data={"email": "flash_agent@example.com", "password": "password123"},
        )

        # Create a ticket
        resp = client.post(
            "/portal/tickets",
            data={
                "category": "hardware",
                "sub_category": "laptop",
                "item": "my laptop",
                "urgency": "low",
                "impact": "individual",
                "description": "To be closed",
            },
            follow_redirects=False,
        )
        # Extract ticket ID from redirect URL
        ticket_id = resp.headers.get("location", "").split("/")[-1]

        # Close the ticket as agent
        client.post(
            f"/agent/tickets/{ticket_id}/transition/close",
            follow_redirects=True,
        )

        # Try to comment on closed ticket
        resp = client.post(
            f"/portal/tickets/{ticket_id}/comments",
            data={"content": "This should fail"},
            follow_redirects=False,
        )
        # Should redirect with flash error (not 400)
        assert resp.status_code == 303
