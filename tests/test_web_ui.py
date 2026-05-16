"""Tests for web UI routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from superticket.db.base import Base
from superticket.main import app
from superticket.models import ticket  # noqa: F401
from superticket.models import user  # noqa: F401
from superticket.models import comment  # noqa: F401


@pytest.fixture(scope="module")
def client():
    """Provide a TestClient with an in-memory database."""
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


@pytest.fixture
def user_client(client):
    """Register a regular user and return client with cookies."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "portaluser@example.com",
            "password": "password123",
            "full_name": "Portal User",
            "role": "user",
        },
    )
    resp = client.post(
        "/login",
        data={"email": "portaluser@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Also get Bearer token for API calls
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "portaluser@example.com", "password": "password123"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return client


@pytest.fixture
def agent_client(client):
    """Register an agent and return client with cookies."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent@example.com",
            "password": "password123",
            "full_name": "Agent User",
            "role": "agent",
        },
    )
    resp = client.post(
        "/login",
        data={"email": "agent@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Also get Bearer token for API calls
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "agent@example.com", "password": "password123"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return client


class TestLoginFlow:
    def test_login_redirects_user_to_portal(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "redirectuser@example.com",
                "password": "password123",
                "full_name": "Redirect User",
                "role": "user",
            },
        )
        resp = client.post(
            "/login",
            data={"email": "redirectuser@example.com", "password": "password123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/portal/"

    def test_login_redirects_user_to_portal(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "redirectuser2@example.com",
                "password": "password123",
                "full_name": "Redirect User2",
            },
        )
        resp = client.post(
            "/login",
            data={"email": "redirectuser2@example.com", "password": "password123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/portal/"

    def test_login_bad_credentials_redirects_with_error(self, client):
        resp = client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "wrong"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login?error=Invalid+email+or+password"

    def test_logout_clears_cookie(self, user_client):
        resp = user_client.get("/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"
        cookies = resp.cookies
        assert "access_token" not in cookies or cookies.get("access_token") == ""

    def test_unauthenticated_redirect_to_login(self, client):
        resp = client.get("/portal/", headers={"Accept": "text/html"}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"


class TestPortalViews:
    def test_portal_dashboard_shows_user_tickets(self, user_client):
        user_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-PORTAL-001",
                "requester_id": "portaluser@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = user_client.get("/portal/")
        assert resp.status_code == 200
        assert "INC-PORTAL-001" in resp.text

    def test_portal_new_ticket_form(self, user_client):
        resp = user_client.get("/portal/tickets/new")
        assert resp.status_code == 200
        assert "Submit New Ticket" in resp.text

    def test_portal_create_ticket(self, user_client):
        resp = user_client.post(
            "/portal/tickets",
            data={
                "category": "Software",
                "sub_category": "Bug",
                "item": "Crash",
                "urgency": "medium",
                "impact": "individual",
                "description": "App crashes",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/portal/tickets/" in resp.headers["location"]

    def test_portal_ticket_detail(self, user_client):
        resp = user_client.get("/portal/tickets/INC-PORTAL-001")
        assert resp.status_code == 200
        assert "Ticket" in resp.text

    def test_portal_add_comment(self, user_client):
        resp = user_client.post(
            "/portal/tickets/INC-PORTAL-001/comments",
            data={"content": "User comment"},
            follow_redirects=False,
        )
        assert resp.status_code == 303


class TestAgentViews:
    def test_agent_dashboard(self, agent_client):
        resp = agent_client.get("/agent/")
        assert resp.status_code in (200, 307)

    def test_agent_ticket_queue(self, agent_client):
        resp = agent_client.get("/agent/tickets")
        assert resp.status_code == 200
        assert "Ticket Queue" in resp.text

    def test_agent_workspace(self, agent_client):
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-AGENT-001",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = agent_client.get("/agent/tickets/INC-AGENT-001/work")
        assert resp.status_code == 200
        assert "Workspace" in resp.text

    def test_agent_state_transition(self, agent_client):
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-AGENT-002",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = agent_client.post(
            "/agent/tickets/INC-AGENT-002/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_agent_add_internal_comment(self, agent_client):
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-AGENT-003",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = agent_client.post(
            "/agent/tickets/INC-AGENT-003/comments",
            data={"content": "Internal note", "is_internal": "true"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_agent_triage_and_assign(self, agent_client):
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-AGENT-004",
                "requester_id": "someone@example.com",
                "category": "Software",
                "sub_category": "Email",
                "item": "Login",
                "urgency": "low",
                "impact": "individual",
            },
        )
        agent_client.post(
            "/agent/tickets/INC-AGENT-004/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        resp = agent_client.post(
            "/agent/tickets/INC-AGENT-004/triage",
            data={
                "category": "Access",
                "sub_category": "Account",
                "item": "Password Reset",
                "urgency": "high",
                "impact": "org",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        resp2 = agent_client.get("/agent/tickets/INC-AGENT-004/work")
        assert "Access" in resp2.text
        assert "assigned" in resp2.text
        assert "P1" in resp2.text


class TestKBEndpoints:
    def test_kb_search_no_params(self, client):
        resp = client.get("/api/v1/kb/search")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10

    def test_kb_search_by_category(self, client):
        resp = client.get("/api/v1/kb/search?category=Hardware")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for article in data:
            assert article["category"] == "Hardware"

    def test_kb_search_by_query(self, client):
        resp = client.get("/api/v1/kb/search?q=password")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        titles = [a["title"] for a in data]
        assert any("password" in t.lower() for t in titles)

    def test_kb_get_article(self, client):
        resp = client.get("/api/v1/kb/reset-password")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "reset-password"
        assert "Reset Your Password" in data["title"]

    def test_kb_article_not_found(self, client):
        resp = client.get("/api/v1/kb/nonexistent")
        assert resp.status_code == 404