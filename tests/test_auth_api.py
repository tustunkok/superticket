"""Tests for auth API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from superticket.db.base import Base
from superticket.main import app
from superticket.models import user  # noqa: F401


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


class TestRegister:
    def test_register_success(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alice@example.com",
                "password": "password123",
                "full_name": "Alice",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "alice@example.com"
        assert data["full_name"] == "Alice"
        assert data["role"] == "user"
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "bob@example.com",
            "password": "password123",
            "full_name": "Bob",
        }
        r1 = client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code == 409

    def test_register_short_password(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "charlie@example.com",
                "password": "short",
                "full_name": "Charlie",
            },
        )
        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "full_name": "Dave",
            },
        )
        assert response.status_code == 422

    def test_register_with_role(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@example.com",
                "password": "password123",
                "full_name": "Admin",
                "role": "admin",
            },
        )
        assert response.status_code == 201
        assert response.json()["role"] == "user"


class TestLogin:
    def test_login_success(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "eve@example.com",
                "password": "password123",
                "full_name": "Eve",
            },
        )
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "eve@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "frank@example.com",
                "password": "password123",
                "full_name": "Frank",
            },
        )
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "frank@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_login_unknown_user(self, client):
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "nobody@example.com", "password": "password123"},
        )
        assert response.status_code == 401


class TestGetMe:
    def test_get_me_authenticated(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "grace@example.com",
                "password": "password123",
                "full_name": "Grace",
            },
        )
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": "grace@example.com", "password": "password123"},
        )
        token = login_resp.json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "grace@example.com"
        assert response.json()["full_name"] == "Grace"

    def test_get_me_no_token(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert response.status_code == 401
