"""SQLAlchemy engine & session factory for SuperTicket."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from superticket.core.config import settings
from superticket.db.base import Base

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables registered on the metadata."""
    Base.metadata.create_all(bind=engine)
