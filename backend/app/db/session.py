"""
SQLAlchemy engine and session factory.

Uses synchronous psycopg2 driver (not asyncpg) to avoid Windows asyncio
event-loop compatibility issues while keeping the API straightforward.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # detect stale connections
    pool_size=5,
    max_overflow=10,
    echo=False,              # set True for SQL query debugging
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db():
    """
    FastAPI dependency that yields a database session and always closes it.
    Use as: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
