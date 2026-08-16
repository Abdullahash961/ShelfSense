"""
SQLAlchemy ORM Models + Database Engine Setup

Defines the two core tables:
  - ``zones``            — shelf zone definitions (coordinates, product, thresholds)
  - ``analysis_results`` — timestamped occupancy readings per zone

Also provides:
  - ``engine``       — the SQLAlchemy engine (SQLite by default)
  - ``SessionLocal`` — a session factory for creating DB sessions
  - ``init_db()``    — creates all tables if they don't exist yet
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    relationship,
    sessionmaker,
)

from config import settings


# ── Base class for all ORM models ──────────────────────────────────────

class Base(DeclarativeBase):
    """Base class that all ORM models inherit from.

    SQLAlchemy uses this to discover tables and generate the schema.
    """
    pass


# ── Zone table ─────────────────────────────────────────────────────────

class ZoneModel(Base):
    """A rectangular region on a shelf that maps to a single product.

    Coordinates (x, y, width, height) are pixel values relative to the
    reference image.
    """
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_name = Column(String, nullable=False)
    product_name = Column(String, default="Unassigned")
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    full_threshold = Column(Float, default=0.50)
    low_threshold = Column(Float, default=0.15)
    reference_image = Column(String, nullable=True)  # path to empty-shelf reference
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship: one zone → many analysis results
    results = relationship(
        "AnalysisResultModel",
        back_populates="zone",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Zone(id={self.id}, name='{self.zone_name}', "
            f"product='{self.product_name}')>"
        )


# ── Analysis result table ──────────────────────────────────────────────

class AnalysisResultModel(Base):
    """A single occupancy reading for one zone at one point in time.

    Each time the system analyses the shelf, it creates one row per zone.
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(
        Integer,
        ForeignKey("zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    fill_score = Column(Float, nullable=False)   # 0.0 – 1.0
    status = Column(String, nullable=False)       # "FULL" / "LOW" / "EMPTY"
    image_path = Column(String, nullable=True)    # which capture was analysed
    analyzed_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship: many results → one zone
    zone = relationship("ZoneModel", back_populates="results")

    def __repr__(self) -> str:
        return (
            f"<AnalysisResult(id={self.id}, zone_id={self.zone_id}, "
            f"status='{self.status}', score={self.fill_score:.2f})>"
        )


# ── Engine & Session setup ─────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + threads
    echo=False,  # set True to see raw SQL in console (useful for debugging)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """Yield a database session, ensuring it's closed after use.

    Usage::

        with get_session() as session:
            zones = session.query(ZoneModel).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables if they don't exist.

    Safe to call multiple times — SQLAlchemy checks for existing tables
    before creating.
    """
    Base.metadata.create_all(bind=engine)
