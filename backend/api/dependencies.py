"""
API Dependencies — Database session and shared utilities.

Provides dependency injection for FastAPI routes.
"""

import sys
import os
from typing import Generator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session to route handlers.

    Usage in routes:
        @router.get("/endpoint")
        def my_endpoint(db: Session = Depends(get_db)):
            result = db.execute(...)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
