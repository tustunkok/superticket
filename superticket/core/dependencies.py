"""FastAPI dependency injection setup."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from superticket.db.engine import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
