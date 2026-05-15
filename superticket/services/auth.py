"""User authentication service — password hashing, JWT, CRUD."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from superticket.core.config import settings
from superticket.core.exceptions import InvalidCredentials
from superticket.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


class AuthService:
    @staticmethod
    def register_user(
        session: Session,
        email: str,
        password: str,
        full_name: str,
        role: str | None = None,
    ) -> User:
        existing = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Email '{email}' is already registered.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role or "user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def authenticate_user(session: Session, email: str, password: str) -> User:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentials
        if not user.is_active:
            raise InvalidCredentials
        return user

    @staticmethod
    def get_user(session: Session, user_id: UUID) -> User | None:
        return session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
