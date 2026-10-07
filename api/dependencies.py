"""
FastAPI Dependency Injection — Database session provider.

All route modules use ``Depends(get_db)`` to receive a per-request
SQLAlchemy session that is automatically closed when the request ends.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from models.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a database session, closing it when the request completes.

    Usage in a route::

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
