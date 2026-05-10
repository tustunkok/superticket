"""Tests for FastAPI ticket endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from superticket.db.base import Base
from superticket.main import app

# Ensure models are registered on Base.metadata before creating tables.
from superticket.models import ticket  # noqa: F401


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

    # Override the get_db dependency for testing
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


class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestCreateTicket:
    def test_create_ticket(self, client):
        response = client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-030",
                "requester_id": "user-30",
                "category": "Hardware",
                "sub_category": "Laptop",
                "item": "Screen",
                "urgency": "high",
                "impact": "individual",
                "priority": "P2",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "INC-2026-030"
        assert data["state"] == "new"

    def test_create_duplicate_id(self, client):
        payload = {
            "id": "INC-2026-031",
            "requester_id": "user-31",
            "category": "Software",
            "sub_category": "Bug",
            "item": "Crash",
            "urgency": "low",
            "impact": "dept",
            "priority": "P3",
        }
        r1 = client.post("/api/v1/tickets", json=payload)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/tickets", json=payload)
        assert r2.status_code == 409  # Integrity error from DB


class TestGetTicket:
    def test_get_existing(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-032",
                "requester_id": "user-32",
                "category": "Network",
                "sub_category": "VPN",
                "item": "Access",
                "urgency": "medium",
                "impact": "org",
                "priority": "P1",
            },
        )
        response = client.get("/api/v1/tickets/INC-2026-032")
        assert response.status_code == 200
        assert response.json()["id"] == "INC-2026-032"

    def test_get_missing(self, client):
        response = client.get("/api/v1/tickets/INC-NOPE")
        assert response.status_code == 404
        assert "TICKET_NOT_FOUND" in response.json()["code"]


class TestListTickets:
    def test_list_pagination(self, client):
        for i in range(3):
            client.post(
                "/api/v1/tickets",
                json={
                    "id": f"INC-2026-{300 + i}",
                    "requester_id": f"user-{i}",
                    "category": "Misc",
                    "sub_category": "Other",
                    "item": "General",
                    "urgency": "low",
                    "impact": "individual",
                    "priority": "P4",
                },
            )
        response = client.get("/api/v1/tickets?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2


class TestUpdateTicket:
    def test_update_allowed_fields(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-033",
                "requester_id": "user-33",
                "category": "Access",
                "sub_category": "Account",
                "item": "Unlock",
                "urgency": "high",
                "impact": "individual",
                "priority": "P2",
            },
        )
        response = client.patch(
            "/api/v1/tickets/INC-2026-033",
            json={"category": "Hardware", "priority": "P1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "Hardware"
        assert data["priority"] == "P1"

    def test_update_disallowed_field(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-034",
                "requester_id": "user-34",
                "category": "Misc",
                "sub_category": "Other",
                "item": "General",
                "urgency": "low",
                "impact": "individual",
                "priority": "P4",
            },
        )
        response = client.patch(
            "/api/v1/tickets/INC-2026-034",
            json={"state": "closed"},
        )
        assert response.status_code == 422

    def test_update_missing_ticket(self, client):
        response = client.patch(
            "/api/v1/tickets/INC-NOPE",
            json={"category": "Hardware"},
        )
        assert response.status_code == 404


class TestTransitionTicket:
    def test_valid_transition(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-035",
                "requester_id": "user-35",
                "category": "Misc",
                "sub_category": "Other",
                "item": "General",
                "urgency": "low",
                "impact": "individual",
                "priority": "P4",
            },
        )
        response = client.post(
            "/api/v1/tickets/INC-2026-035/transition",
            json={"target_state": "assigned", "performed_by": "dispatcher"},
        )
        assert response.status_code == 200
        assert response.json()["state"] == "assigned"

    def test_invalid_transition(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-036",
                "requester_id": "user-36",
                "category": "Misc",
                "sub_category": "Other",
                "item": "General",
                "urgency": "low",
                "impact": "individual",
                "priority": "P4",
            },
        )
        response = client.post(
            "/api/v1/tickets/INC-2026-036/transition",
            json={"target_state": "closed"},
        )
        assert response.status_code == 400
        assert "INVALID_STATE_TRANSITION" in response.json()["code"]

    def test_transition_missing_ticket(self, client):
        response = client.post(
            "/api/v1/tickets/INC-NOPE/transition",
            json={"target_state": "assigned"},
        )
        assert response.status_code == 404


class TestAuditLog:
    def test_get_audit_log(self, client):
        client.post(
            "/api/v1/tickets",
            json={
                "id": "INC-2026-037",
                "requester_id": "user-37",
                "category": "Misc",
                "sub_category": "Other",
                "item": "General",
                "urgency": "low",
                "impact": "individual",
                "priority": "P4",
            },
        )
        client.post(
            "/api/v1/tickets/INC-2026-037/transition",
            json={"target_state": "assigned"},
        )
        response = client.get("/api/v1/tickets/INC-2026-037/audit")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 2  # created + state_transition
        assert logs[0]["action"] == "created"
        assert logs[1]["action"] == "state_transition"

    def test_get_audit_missing_ticket(self, client):
        response = client.get("/api/v1/tickets/INC-NOPE/audit")
        assert response.status_code == 404
