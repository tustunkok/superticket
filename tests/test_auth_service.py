"""Tests for the AuthService layer."""

import uuid

import pytest
from jose import jwt

from superticket.core.exceptions import InvalidCredentials
from superticket.services.auth import (
    AuthService,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "super-secret-password"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_create_and_decode_token(self):
        data = {"sub": str(uuid.uuid4()), "email": "test@example.com"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == data["sub"]
        assert decoded["email"] == data["email"]
        assert "exp" in decoded

    def test_decode_invalid_token(self):
        with pytest.raises(jwt.JWTError):
            decode_access_token("not-a-valid-token")


class TestRegisterUser:
    def test_register_creates_user(self, db_session):
        user = AuthService.register_user(
            db_session, email="alice@example.com", password="password123", full_name="Alice"
        )
        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.full_name == "Alice"
        assert user.role == "user"
        assert user.is_active is True

    def test_register_password_is_hashed(self, db_session):
        user = AuthService.register_user(
            db_session, email="bob@example.com", password="password123", full_name="Bob"
        )
        assert user.hashed_password != "password123"
        assert verify_password("password123", user.hashed_password)

    def test_register_duplicate_email_raises(self, db_session):
        AuthService.register_user(
            db_session, email="dup@example.com", password="password123", full_name="First"
        )
        with pytest.raises(ValueError, match="already registered"):
            AuthService.register_user(
                db_session, email="dup@example.com", password="password456", full_name="Second"
            )

    def test_register_with_role(self, db_session):
        user = AuthService.register_user(
            db_session, email="admin@example.com", password="password123", full_name="Admin", role="admin"
        )
        assert user.role == "admin"


class TestAuthenticateUser:
    def test_authenticate_valid_credentials(self, db_session):
        AuthService.register_user(
            db_session, email="charlie@example.com", password="password123", full_name="Charlie"
        )
        user = AuthService.authenticate_user(db_session, "charlie@example.com", "password123")
        assert user.email == "charlie@example.com"

    def test_authenticate_wrong_password(self, db_session):
        AuthService.register_user(
            db_session, email="dave@example.com", password="password123", full_name="Dave"
        )
        with pytest.raises(InvalidCredentials):
            AuthService.authenticate_user(db_session, "dave@example.com", "wrong")

    def test_authenticate_unknown_email(self, db_session):
        with pytest.raises(InvalidCredentials):
            AuthService.authenticate_user(db_session, "nobody@example.com", "password123")

    def test_get_user(self, db_session):
        created = AuthService.register_user(
            db_session, email="eve@example.com", password="password123", full_name="Eve"
        )
        fetched = AuthService.get_user(db_session, created.id)
        assert fetched is not None
        assert fetched.email == "eve@example.com"

    def test_get_user_missing(self, db_session):
        assert AuthService.get_user(db_session, uuid.uuid4()) is None
