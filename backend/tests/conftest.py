"""
conftest.py — shared pytest fixtures for Campus OS backend tests.

Test database strategy:
    Tests use a separate TEST_DATABASE_URL (see .env.example).
    Each test module that needs DB access gets a fresh transaction that
    is rolled back after the test — this keeps tests isolated and fast.

Date injection:
    Tests override settings.today via dependency injection where needed.
    The DEMO_TODAY env var can also be set for integration tests.

⚠  Tests use SYNTHETIC data only.  No real institutional data is used.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app

# ── Test database URL ─────────────────────────────────────────────────────
# Uses settings.TEST_DATABASE_URL or TEST_DATABASE_URL env var.
# Isolation: tests ALWAYS use a separate DB to avoid corrupting dev data.

TEST_DATABASE_URL: str = (
    os.environ.get("TEST_DATABASE_URL")
    or settings.TEST_DATABASE_URL
)

# Safety assertion: tests MUST NOT use the main database
if TEST_DATABASE_URL == settings.DATABASE_URL:
    raise RuntimeError(
        f"SAFETY CHECK FAILED: TEST_DATABASE_URL ({TEST_DATABASE_URL}) "
        f"must not match development DATABASE_URL ({settings.DATABASE_URL})."
    )


@pytest.fixture(scope="session")
def test_engine():
    """
    Session-scoped engine pointing at the test database.
    Creates all tables and seeds demo data once per test session.
    Drops them at teardown.
    """
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        from app.db.seed import run_seed
        run_seed(session)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Function-scoped database session.
    Runs inside a connection savepoint that is rolled back on teardown,
    ensuring test isolation without modifying the seeded baseline.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    FastAPI TestClient with the DB session dependency overridden.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seeded_client(db_session: Session):
    """
    FastAPI TestClient with access to the seeded test database.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

