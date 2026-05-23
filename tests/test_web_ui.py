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


def _set_user_role(email: str, role: str) -> None:
    """Update a user's role in the test database (bypasses schema for tests)."""
    from superticket.core.dependencies import get_db
    from superticket.models.user import User
    from sqlalchemy import select

    override = app.dependency_overrides.get(get_db)
    if not override:
        return
    db = next(override())
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user:
            user.role = role
            db.commit()
    finally:
        db.close()


@pytest.fixture
def agent_client(client):
    """Register an agent and return client with cookies."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent@example.com",
            "password": "password123",
            "full_name": "Agent User",
        },
    )
    _set_user_role("agent@example.com", "agent")
    resp = client.post(
        "/login",
        data={"email": "agent@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
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

    def test_login_redirects_default_user_to_portal(self, client):
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
        # Flash messages are stored in session cookie, not query params
        assert resp.headers["location"] == "/login"

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

    def test_agent_workspace_shows_requester(self, agent_client):
        """Test that agent workspace shows requester name and email."""
        # Create a user first
        agent_client.post(
            "/api/v1/auth/register",
            json={
                "email": "requester@example.com",
                "password": "password123",
                "full_name": "Requester User",
            },
        )
        # Create a ticket with requester_id as email
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-REQ-001",
                "requester_id": "requester@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = agent_client.get("/agent/tickets/INC-REQ-001/work")
        assert resp.status_code == 200
        assert "Requester User" in resp.text
        assert "requester@example.com" in resp.text

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


@pytest.fixture
def admin_client(client):
    """Register an admin and return client with cookies."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin_test@example.com",
            "password": "password123",
            "full_name": "Admin Test",
        },
    )
    _set_user_role("admin_test@example.com", "admin")
    resp = client.post(
        "/login",
        data={"email": "admin_test@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "admin_test@example.com", "password": "password123"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return client


class TestRootRedirect:
    """Bug 3: root route should redirect authenticated users to their dashboard."""

    def test_unauthenticated_redirects_to_login(self, client):
        client.cookies.pop("access_token", None)
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 303, 307)
        assert resp.headers["location"] == "/login"

    def test_authenticated_user_redirects_to_portal(self, user_client):
        resp = user_client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 303, 307)
        assert resp.headers["location"] == "/portal/"

    def test_authenticated_agent_redirects_to_agent_tickets(self, agent_client):
        resp = agent_client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 303, 307)
        assert resp.headers["location"] == "/agent/tickets"

    def test_authenticated_admin_redirects_to_agent_tickets(self, admin_client):
        resp = admin_client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 303, 307)
        assert resp.headers["location"] == "/agent/tickets"


class TestAgentRoleGuard:
    """Bug 4: Agent routes enforce role guard."""

    def test_regular_user_forbidden_on_dashboard(self, user_client):
        resp = user_client.get("/agent/", follow_redirects=False)
        assert resp.status_code == 403

    def test_regular_user_forbidden_on_ticket_queue(self, user_client):
        resp = user_client.get("/agent/tickets", follow_redirects=False)
        assert resp.status_code == 403

    def test_agent_can_access_dashboard(self, agent_client):
        resp = agent_client.get("/agent/", follow_redirects=False)
        assert resp.status_code in (200, 307)

    def test_agent_can_access_ticket_queue(self, agent_client):
        resp = agent_client.get("/agent/tickets")
        assert resp.status_code == 200

    def test_admin_can_access_dashboard(self, admin_client):
        resp = admin_client.get("/agent/", follow_redirects=False)
        assert resp.status_code in (200, 307)

    def test_admin_can_access_ticket_queue(self, admin_client):
        resp = admin_client.get("/agent/tickets")
        assert resp.status_code == 200

    def test_regular_user_forbidden_on_workspace(self, user_client, agent_client):
        """Regular user cannot access ticket workspace."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ROLEGUARD-001",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        user_client.post(
            "/login",
            data={"email": "portaluser@example.com", "password": "password123"},
            follow_redirects=False,
        )
        resp = user_client.get("/agent/tickets/INC-ROLEGUARD-001/work", follow_redirects=False)
        assert resp.status_code == 403

    def test_regular_user_forbidden_on_comment(self, user_client, agent_client):
        """Regular user cannot add comments via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ROLEGUARD-002",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        user_client.post(
            "/login",
            data={"email": "portaluser@example.com", "password": "password123"},
            follow_redirects=False,
        )
        resp = user_client.post(
            "/agent/tickets/INC-ROLEGUARD-002/comments",
            data={"content": "Unauthorized comment", "is_internal": "false"},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_regular_user_forbidden_on_transition(self, user_client, agent_client):
        """Regular user cannot transition tickets via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ROLEGUARD-003",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        user_client.post(
            "/login",
            data={"email": "portaluser@example.com", "password": "password123"},
            follow_redirects=False,
        )
        resp = user_client.post(
            "/agent/tickets/INC-ROLEGUARD-003/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_regular_user_forbidden_on_triage(self, user_client, agent_client):
        """Regular user cannot triage tickets via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ROLEGUARD-004",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        agent_client.post(
            "/agent/tickets/INC-ROLEGUARD-004/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        user_client.post(
            "/login",
            data={"email": "portaluser@example.com", "password": "password123"},
            follow_redirects=False,
        )
        resp = user_client.post(
            "/agent/tickets/INC-ROLEGUARD-004/triage",
            data={
                "category": "Access",
                "sub_category": "Account",
                "item": "Password Reset",
                "urgency": "high",
                "impact": "org",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_admin_can_access_workspace(self, admin_client, agent_client):
        """Admin can access ticket workspace."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ADMIN-WORKSPACE",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = admin_client.get("/agent/tickets/INC-ADMIN-WORKSPACE/work")
        assert resp.status_code == 200

    def test_admin_can_transition_ticket(self, admin_client, agent_client):
        """Admin can transition tickets via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ADMIN-TRANSITION",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = admin_client.post(
            "/agent/tickets/INC-ADMIN-TRANSITION/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_admin_can_add_comment(self, admin_client, agent_client):
        """Admin can add comments via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ADMIN-COMMENT",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        resp = admin_client.post(
            "/agent/tickets/INC-ADMIN-COMMENT/comments",
            data={"content": "Admin comment", "is_internal": "true"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_admin_can_triage_ticket(self, admin_client, agent_client):
        """Admin can triage tickets via agent route."""
        agent_client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-ADMIN-TRIAGE",
                "requester_id": "someone@example.com",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
            },
        )
        agent_client.post(
            "/agent/tickets/INC-ADMIN-TRIAGE/transition",
            data={"target_state": "triage"},
            follow_redirects=False,
        )
        resp = admin_client.post(
            "/agent/tickets/INC-ADMIN-TRIAGE/triage",
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