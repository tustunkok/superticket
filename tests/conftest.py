"""Pytest fixtures and configuration for SuperTicket tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from superticket.db.base import Base

from superticket.models import ticket  # noqa: F401
from superticket.models import user  # noqa: F401
from superticket.models import comment  # noqa: F401
from superticket.models import triage_log  # noqa: F401


@pytest.fixture(scope="session")
def engine():
    """Create a SQLite in-memory engine for the test session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a fresh transaction-scoped session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
