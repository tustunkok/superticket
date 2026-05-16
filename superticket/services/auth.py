"""User authentication service — password hashing, JWT, CRUD."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from superticket.core.config import settings
from superticket.core.exceptions import InvalidCredentials
from superticket.models.enums import UserRole
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

    @staticmethod
    def list_users(
        session: Session,
        skip: int = 0,
        limit: int = 100,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        query = select(User)
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        total = session.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
        users = list(
            session.execute(query.order_by(User.email).offset(skip).limit(limit)).scalars().all()
        )
        return users, total

    @staticmethod
    def update_user_role(session: Session, user_id: UUID, new_role: str) -> User:
        if new_role not in (r.value for r in UserRole):
            raise ValueError(f"Invalid role: {new_role}")
        user = AuthService.get_user(session, user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        user.role = new_role
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def set_user_active(session: Session, user_id: UUID, is_active: bool, performed_by: User) -> User:
        if user_id == performed_by.id:
            raise ValueError("Cannot change your own active status.")
        user = AuthService.get_user(session, user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        user.is_active = is_active
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def delete_user(session: Session, user_id: UUID, performed_by: User) -> None:
        if user_id == performed_by.id:
            raise ValueError("Cannot delete your own account.")
        user = AuthService.get_user(session, user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        session.delete(user)
        session.commit()
