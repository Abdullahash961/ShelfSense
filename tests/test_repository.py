"""
Tests for the database repository layer.

Uses an in-memory SQLite database so tests are fast, isolated, and don't
touch the real database file.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, ZoneModel, AnalysisResultModel
from db.repository import ZoneRepository, AnalysisRepository


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def session():
    """Create a fresh in-memory SQLite database for each test.

    This means every test starts with an empty database — no leftover
    data from previous tests can interfere.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    sess = TestSession()
    yield sess
    sess.close()


@pytest.fixture
def zone_repo(session):
    """ZoneRepository backed by the in-memory test database."""
    return ZoneRepository(session)


@pytest.fixture
def analysis_repo(session):
    """AnalysisRepository backed by the in-memory test database."""
    return AnalysisRepository(session)


def _create_sample_zone(repo: ZoneRepository, name: str = "Zone A") -> ZoneModel:
    """Helper to create a zone with default values."""
    return repo.create(
        zone_name=name,
        product_name="Test Product",
        x=10, y=20, width=100, height=50,
        full_threshold=0.50,
        low_threshold=0.15,
        reference_image="empty_shelf.png",
    )


# ── Zone Repository tests ─────────────────────────────────────────────

class TestZoneRepository:

    def test_create_zone(self, zone_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        assert zone.id is not None
        assert zone.zone_name == "Zone A"
        assert zone.product_name == "Test Product"
        assert zone.x == 10
        assert zone.width == 100

    def test_get_all_empty(self, zone_repo):
        assert zone_repo.get_all() == []

    def test_get_all_returns_all(self, zone_repo, session):
        _create_sample_zone(zone_repo, "Zone A")
        _create_sample_zone(zone_repo, "Zone B")
        _create_sample_zone(zone_repo, "Zone C")
        session.commit()

        zones = zone_repo.get_all()
        assert len(zones) == 3
        assert [z.zone_name for z in zones] == ["Zone A", "Zone B", "Zone C"]

    def test_get_by_id_found(self, zone_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        found = zone_repo.get_by_id(zone.id)
        assert found is not None
        assert found.zone_name == "Zone A"

    def test_get_by_id_not_found(self, zone_repo):
        assert zone_repo.get_by_id(999) is None

    def test_update_zone(self, zone_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        updated = zone_repo.update(zone.id, zone_name="Zone A Updated", x=50)
        session.commit()

        assert updated.zone_name == "Zone A Updated"
        assert updated.x == 50
        # Unchanged fields stay the same
        assert updated.product_name == "Test Product"
        assert updated.y == 20

    def test_update_nonexistent_returns_none(self, zone_repo):
        assert zone_repo.update(999, zone_name="Ghost") is None

    def test_delete_zone(self, zone_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        assert zone_repo.delete(zone.id) is True
        session.commit()

        assert zone_repo.get_by_id(zone.id) is None
        assert zone_repo.count() == 0

    def test_delete_nonexistent_returns_false(self, zone_repo):
        assert zone_repo.delete(999) is False

    def test_count(self, zone_repo, session):
        assert zone_repo.count() == 0
        _create_sample_zone(zone_repo, "Zone A")
        _create_sample_zone(zone_repo, "Zone B")
        session.commit()
        assert zone_repo.count() == 2


# ── Analysis Repository tests ─────────────────────────────────────────

class TestAnalysisRepository:

    def test_save_result(self, zone_repo, analysis_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        result = analysis_repo.save_result(
            zone_id=zone.id,
            fill_score=0.75,
            status="FULL",
            image_path="test.png",
        )
        session.commit()

        assert result.id is not None
        assert result.fill_score == 0.75
        assert result.status == "FULL"

    def test_save_batch(self, zone_repo, analysis_repo, session):
        z1 = _create_sample_zone(zone_repo, "Zone A")
        z2 = _create_sample_zone(zone_repo, "Zone B")
        session.commit()

        results = analysis_repo.save_batch([
            {"zone_id": z1.id, "fill_score": 0.80, "status": "FULL", "image_path": "t.png"},
            {"zone_id": z2.id, "fill_score": 0.10, "status": "EMPTY", "image_path": "t.png"},
        ])
        session.commit()

        assert len(results) == 2
        assert analysis_repo.count() == 2

    def test_get_latest(self, zone_repo, analysis_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        # Save two results for the same zone — different timestamps
        analysis_repo.save_result(
            zone_id=zone.id, fill_score=0.30, status="LOW",
            image_path="old.png",
            analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        analysis_repo.save_result(
            zone_id=zone.id, fill_score=0.80, status="FULL",
            image_path="new.png",
            analyzed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        session.commit()

        latest = analysis_repo.get_latest()
        assert len(latest) == 1                 # One zone → one latest
        assert latest[0].fill_score == 0.80     # The newer one
        assert latest[0].status == "FULL"

    def test_get_history(self, zone_repo, analysis_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        for i in range(5):
            analysis_repo.save_result(
                zone_id=zone.id, fill_score=i * 0.2, status="LOW",
                image_path=f"img_{i}.png",
            )
        session.commit()

        history = analysis_repo.get_history(zone.id, limit=3)
        assert len(history) == 3  # Limited to 3

    def test_get_alerts(self, zone_repo, analysis_repo, session):
        z1 = _create_sample_zone(zone_repo, "Zone A")
        z2 = _create_sample_zone(zone_repo, "Zone B")
        z3 = _create_sample_zone(zone_repo, "Zone C")
        session.commit()

        analysis_repo.save_result(
            zone_id=z1.id, fill_score=0.80, status="FULL", image_path="t.png",
        )
        analysis_repo.save_result(
            zone_id=z2.id, fill_score=0.05, status="EMPTY", image_path="t.png",
        )
        analysis_repo.save_result(
            zone_id=z3.id, fill_score=0.20, status="LOW", image_path="t.png",
        )
        session.commit()

        alerts = analysis_repo.get_alerts()
        assert len(alerts) == 2  # EMPTY + LOW, not FULL
        statuses = {a.status for a in alerts}
        assert statuses == {"EMPTY", "LOW"}

    def test_count(self, zone_repo, analysis_repo, session):
        zone = _create_sample_zone(zone_repo)
        session.commit()

        assert analysis_repo.count() == 0
        analysis_repo.save_result(
            zone_id=zone.id, fill_score=0.50, status="FULL", image_path="t.png",
        )
        session.commit()
        assert analysis_repo.count() == 1
