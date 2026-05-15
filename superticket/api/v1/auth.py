"""User authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from superticket.core.dependencies import get_current_active_user, get_db
from superticket.models.user import User
from superticket.schemas.user import Token, UserCreate, UserOut
from superticket.services.auth import AuthService, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """Register a new user account."""
    try:
        user = AuthService.register_user(
            db,
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            role=data.role.value if data.role else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return user


@router.post("/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate user and return a JWT access token."""
    from superticket.core.exceptions import InvalidCredentials

    try:
        user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_active_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return current_user
