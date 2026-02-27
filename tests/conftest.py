"""Shared test fixtures and configuration for the GreenPulse 2.0 test suite."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use a test-specific SQLite DB or the configured DATABASE_URL
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://greenpulse:greenpulse123@localhost:5432/greenpulse_db",
)


@pytest.fixture(scope="session")
def db_engine():
    """Create a SQLAlchemy engine for the test session."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Provide a transactional database session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
