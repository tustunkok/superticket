"""FastAPI dependency injection setup."""

from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from superticket.db.engine import SessionLocal
from superticket.models.enums import UserRole
from superticket.models.user import User
from superticket.services.auth import AuthService, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_db() -> Generator[Session, None, None]:
    """Yield a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_user_from_token(token: str, db: Session) -> User:
    """Decode JWT and return the authenticated user."""
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )

    user = AuthService.get_user(db, UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT from Authorization header and return the authenticated user."""
    return _get_user_from_token(token, db)


def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT from cookie and return the authenticated user."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    return _get_user_from_token(token, db)


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require an authenticated, active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )
    return current_user


def get_current_active_user_from_cookie(
    current_user: User = Depends(get_current_user_from_cookie),
) -> User:
    """Require an authenticated, active user (cookie-based)."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )
    return current_user


def get_optional_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Decode JWT from cookie and return the user, or None if not authenticated."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return _get_user_from_token(token, db)
    except HTTPException:
        return None


def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require an authenticated, active admin user (API)."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def require_admin_cookie(
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> User:
    """Require an authenticated, active admin user (cookie-based)."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def require_agent_or_admin_cookie(
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> User:
    """Require an authenticated, active agent or admin user (cookie-based)."""
    if current_user.role not in (UserRole.AGENT.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or admin access required.",
        )
    return current_user
