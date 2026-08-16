"""
Repository Layer — All database CRUD operations.

Two repository classes isolate every DB interaction:
  - ``ZoneRepository``     — create / read / update / delete zones
  - ``AnalysisRepository`` — save and query analysis results

The rest of the application calls these methods instead of writing raw SQL.
If you ever swap SQLite for Postgres, only this file changes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models.database import AnalysisResultModel, ZoneModel


# ── Zone Repository ────────────────────────────────────────────────────

class ZoneRepository:
    """CRUD operations for shelf zones.

    Each method receives a SQLAlchemy ``Session`` so the caller controls
    the transaction boundary (commit / rollback).
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> list[ZoneModel]:
        """Return all zones, ordered by ID."""
        return (
            self.session
            .query(ZoneModel)
            .order_by(ZoneModel.id)
            .all()
        )

    def get_by_id(self, zone_id: int) -> ZoneModel | None:
        """Return a single zone by primary key, or None if not found."""
        return self.session.get(ZoneModel, zone_id)

    def create(self, **kwargs) -> ZoneModel:
        """Create a new zone and flush it to get the auto-generated ID.

        Args:
            **kwargs: Column values (zone_name, product_name, x, y, ...).

        Returns:
            The newly created ZoneModel (with ``.id`` populated).
        """
        zone = ZoneModel(**kwargs)
        self.session.add(zone)
        self.session.flush()  # assigns the ID without committing
        return zone

    def update(self, zone_id: int, **kwargs) -> ZoneModel | None:
        """Update an existing zone's fields.

        Only non-None kwargs are applied, so you can do partial updates.

        Returns:
            The updated ZoneModel, or None if zone_id doesn't exist.
        """
        zone = self.get_by_id(zone_id)
        if zone is None:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(zone, key):
                setattr(zone, key, value)

        self.session.flush()
        return zone

    def delete(self, zone_id: int) -> bool:
        """Delete a zone by ID.

        Returns:
            True if deleted, False if zone_id didn't exist.
        """
        zone = self.get_by_id(zone_id)
        if zone is None:
            return False

        self.session.delete(zone)
        self.session.flush()
        return True

    def count(self) -> int:
        """Return the total number of zones."""
        return self.session.query(func.count(ZoneModel.id)).scalar()


# ── Analysis Repository ────────────────────────────────────────────────

class AnalysisRepository:
    """Store and query shelf analysis results.

    Results are always associated with a zone (via ``zone_id``).
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_result(self, **kwargs) -> AnalysisResultModel:
        """Save a single analysis result.

        Args:
            **kwargs: Column values (zone_id, fill_score, status, ...).

        Returns:
            The newly created AnalysisResultModel.
        """
        result = AnalysisResultModel(**kwargs)
        self.session.add(result)
        self.session.flush()
        return result

    def save_batch(self, results: list[dict]) -> list[AnalysisResultModel]:
        """Save multiple analysis results at once (one per zone).

        Args:
            results: List of dicts with column values.

        Returns:
            List of newly created AnalysisResultModel objects.
        """
        models = [AnalysisResultModel(**r) for r in results]
        self.session.add_all(models)
        self.session.flush()
        return models

    def get_latest(self) -> list[AnalysisResultModel]:
        """Get the most recent result for each zone.

        Uses a subquery to find the max ``analyzed_at`` per zone, then
        joins back to get the full rows.

        Returns:
            List of the latest AnalysisResultModel per zone.
        """
        # Subquery: latest timestamp per zone
        latest_sub = (
            self.session
            .query(
                AnalysisResultModel.zone_id,
                func.max(AnalysisResultModel.analyzed_at).label("max_at"),
            )
            .group_by(AnalysisResultModel.zone_id)
            .subquery()
        )

        # Join back to get full rows
        return (
            self.session
            .query(AnalysisResultModel)
            .join(
                latest_sub,
                (AnalysisResultModel.zone_id == latest_sub.c.zone_id)
                & (AnalysisResultModel.analyzed_at == latest_sub.c.max_at),
            )
            .all()
        )

    def get_history(
        self,
        zone_id: int,
        limit: int = 50,
    ) -> list[AnalysisResultModel]:
        """Get the N most recent results for a specific zone (newest first).

        Useful for trend charts on the dashboard.
        """
        return (
            self.session
            .query(AnalysisResultModel)
            .filter(AnalysisResultModel.zone_id == zone_id)
            .order_by(desc(AnalysisResultModel.analyzed_at))
            .limit(limit)
            .all()
        )

    def get_alerts(
        self,
        statuses: list[str] | None = None,
    ) -> list[AnalysisResultModel]:
        """Get the latest results that match alert statuses (default: LOW + EMPTY).

        Returns only the most recent reading per zone, filtered to zones
        that need attention.
        """
        if statuses is None:
            statuses = ["LOW", "EMPTY"]

        latest = self.get_latest()
        return [r for r in latest if r.status in statuses]

    def count(self) -> int:
        """Return the total number of stored analysis results."""
        return self.session.query(func.count(AnalysisResultModel.id)).scalar()
