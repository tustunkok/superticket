"""Tests for FastAPI triage endpoints."""

from dataclasses import dataclass

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
from superticket.models import triage_log  # noqa: F401


@dataclass
class _MockUser:
    email: str = "testuser@example.com"
    is_active: bool = True
    role: str = "agent"


@pytest.fixture(scope="module")
def client():
    """Provide a TestClient with an in-memory database and auth bypass."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from superticket.core.dependencies import get_current_active_user, get_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_active_user():
        return _MockUser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _create_ticket_with_ai(client, tid):
    """Create a ticket and manually set AI triage fields via PATCH."""
    client.post(
        "/api/v1/tickets",
        json={
            "id": tid,
            "requester_id": "user-ai",
            "category": "Network",
            "sub_category": "VPN",
            "item": "Access",
            "urgency": "low",
            "impact": "individual",
            "description": "Cannot connect to VPN",
        },
    )
    client.post(
        f"/api/v1/tickets/{tid}/transition",
        json={"target_state": "triage"},
    )
    return tid


class TestTriageGet:
    def test_get_triage_no_results(self, client):
        """Ticket without AI results returns 404."""
        _create_ticket_with_ai(client, "INC-TRIAGE-API-01")

        response = client.get("/api/v1/tickets/INC-TRIAGE-API-01/triage")
        assert response.status_code == 404

    def test_get_triage_missing_ticket(self, client):
        """Non-existent ticket returns 404."""
        response = client.get("/api/v1/tickets/INC-NOPE/triage")
        assert response.status_code == 404


class TestTriageConfirm:
    def test_confirm_success(self, client):
        """Successfully confirm triage with override reason."""
        tid = _create_ticket_with_ai(client, "INC-TRIAGE-API-02")

        # Simulate AI setting fields via PATCH (normally done by LLM)
        response = client.patch(
            f"/api/v1/tickets/{tid}",
            json={
                "category": "Network",
                "sub_category": "VPN",
                "item": "Access",
            },
        )
        assert response.status_code == 200

        # Now confirm via triage endpoint
        response = client.post(
            f"/api/v1/tickets/{tid}/triage/confirm",
            json={
                "category": "Network",
                "sub_category": "VPN",
                "item": "Access",
                "override_reason": None,
            },
        )
        assert response.status_code == 200

    def test_confirm_not_triage_state(self, client):
        """Cannot confirm triage for ticket not in TRIAGE state."""
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-TRIAGE-API-03",
                "requester_id": "user-ai",
                "category": "Network",
                "sub_category": "VPN",
                "item": "Access",
                "urgency": "low",
                "impact": "individual",
            },
        )

        response = client.post(
            "/api/v1/tickets/INC-TRIAGE-API-03/triage/confirm",
            json={"category": "Network", "sub_category": "VPN", "item": "Access"},
        )
        assert response.status_code == 409

    def test_confirm_missing_ticket(self, client):
        """Non-existent ticket returns 404."""
        response = client.post(
            "/api/v1/tickets/INC-NOPE/triage/confirm",
            json={"category": "Network"},
        )
        assert response.status_code == 404
