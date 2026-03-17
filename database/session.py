"""
Database engine and session factory.

Usage:
    from database.session import get_engine, get_session

    engine = get_engine()
    with get_session() as session:
        result = session.execute(text("SELECT 1"))
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from config import settings
from loguru import logger


def get_engine(echo: bool = False):
    """
    Create a SQLAlchemy engine connected to PostgreSQL.

    Args:
        echo: If True, log all SQL statements (useful for debugging).
    """
    engine = create_engine(
        settings.database_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    logger.info(f"Database engine created: {settings.database_url.split('@')[1]}")
    return engine


# Default engine (created once at import time)
engine = get_engine()

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """
    Get a database session. Use as context manager:

        with get_session() as session:
            session.execute(...)
    """
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.rollback()
        raise
