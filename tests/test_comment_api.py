"""Tests for Comment API endpoints."""

import uuid

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


@pytest.fixture(scope="module")
def user_token(client):
    """Register and login a user, returning a bearer token."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "commenter@example.com",
            "password": "password123",
            "full_name": "Commenter",
        },
    )
    login = client.post(
        "/api/v1/auth/token",
        data={"username": "commenter@example.com", "password": "password123"},
    )
    return login.json()["access_token"]


@pytest.fixture
def sample_ticket(client, user_token):
    """Create a fresh ticket for each test, returning its ID."""
    ticket_id = f"INC-COMMENT-{uuid.uuid4().hex[:8].upper()}"
    resp = client.post(
        "/api/v1/tickets",
        json={
            "id": ticket_id,
            "requester_id": "user-001",
            "category": "Hardware",
            "sub_category": "Laptop",
            "item": "Screen",
            "urgency": "high",
            "impact": "individual",
            "description": "Screen is black",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    return resp.json()["id"]


class TestCreateComment:
    def test_create_comment(self, client, user_token, sample_ticket):
        response = client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "This is a comment", "is_internal": False},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "This is a comment"
        assert data["is_internal"] is False
        assert data["author_name"] == "Commenter"
        assert data["ticket_id"] == sample_ticket

    def test_create_internal_comment(self, client, user_token, sample_ticket):
        response = client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "Internal note", "is_internal": True},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 201
        assert response.json()["is_internal"] is True

    def test_create_comment_missing_ticket(self, client, user_token):
        response = client.post(
            "/api/v1/tickets/INC-NOPE/comments",
            json={"content": "Will fail", "is_internal": False},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 404

    def test_create_comment_unauthorized(self, client, sample_ticket):
        response = client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "No auth", "is_internal": False},
        )
        assert response.status_code == 401


class TestListComments:
    def test_list_comments(self, client, user_token, sample_ticket):
        # Create a few comments first
        client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "First", "is_internal": False},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "Second", "is_internal": True},
            headers={"Authorization": f"Bearer {user_token}"},
        )

        response = client.get(
            f"/api/v1/tickets/{sample_ticket}/comments",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        contents = {c["content"] for c in data}
        assert contents == {"First", "Second"}

    def test_list_comments_exclude_internal(self, client, user_token, sample_ticket):
        # Setup: create one public and one internal comment
        client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "Public comment", "is_internal": False},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        client.post(
            f"/api/v1/tickets/{sample_ticket}/comments",
            json={"content": "Internal note", "is_internal": True},
            headers={"Authorization": f"Bearer {user_token}"},
        )

        response = client.get(
            f"/api/v1/tickets/{sample_ticket}/comments?include_internal=false",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Public comment"
        assert not data[0]["is_internal"]

    def test_list_comments_pagination(self, client, user_token, sample_ticket):
        # Setup: create multiple comments
        for i in range(3):
            client.post(
                f"/api/v1/tickets/{sample_ticket}/comments",
                json={"content": f"Comment {i}", "is_internal": False},
                headers={"Authorization": f"Bearer {user_token}"},
            )

        response = client.get(
            f"/api/v1/tickets/{sample_ticket}/comments?limit=1",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_comments_missing_ticket(self, client, user_token):
        response = client.get(
            "/api/v1/tickets/INC-NOPE/comments",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 404

    def test_list_comments_unauthorized(self, client, sample_ticket):
        response = client.get(f"/api/v1/tickets/{sample_ticket}/comments")
        assert response.status_code == 401
