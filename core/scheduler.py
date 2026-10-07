"""
Analysis Scheduler — Background job that captures + analyses shelves on a timer.

Uses APScheduler's ``BackgroundScheduler`` to run a full capture-and-analyse
cycle at a configurable interval (default: every 5 minutes).

Lifecycle is managed by the FastAPI lifespan context so the scheduler
starts on server boot and stops cleanly on shutdown.

Usage::

    from core.scheduler import analysis_scheduler

    analysis_scheduler.start()     # begin periodic analysis
    analysis_scheduler.stop()      # stop cleanly
    analysis_scheduler.trigger()   # run one cycle right now
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

logger = logging.getLogger(__name__)

_JOB_ID = "shelfsense_analysis_cycle"


class AnalysisScheduler:
    """Periodically captures a camera frame and runs the CV pipeline.

    Attributes:
        running:      Whether the scheduler is currently active.
        interval_min: The interval between cycles in minutes.
        last_run:     Timestamp of the most recent completed cycle.
        last_status:  Summary string from the last cycle.
        next_run:     Scheduled time for the next cycle.
    """

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(daemon=True)
        self._interval_min: int = settings.ANALYSIS_INTERVAL_MINUTES
        self._last_run: datetime | None = None
        self._last_status: str = "never"
        self._cycle_count: int = 0

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._scheduler.running

    @property
    def interval_min(self) -> int:
        return self._interval_min

    @property
    def last_run(self) -> datetime | None:
        return self._last_run

    @property
    def last_status(self) -> str:
        return self._last_status

    @property
    def next_run(self) -> datetime | None:
        job = self._scheduler.get_job(_JOB_ID)
        if job and job.next_run_time:
            return job.next_run_time
        return None

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ── Start / Stop ────────────────────────────────────────────────────

    def start(self, interval_minutes: int | None = None) -> None:
        """Start the periodic analysis scheduler.

        Args:
            interval_minutes: Override the default interval (from settings).
        """
        if self.running:
            logger.warning("Scheduler is already running")
            return

        if interval_minutes is not None:
            self._interval_min = interval_minutes

        self._scheduler.add_job(
            self._run_cycle,
            trigger=IntervalTrigger(minutes=self._interval_min),
            id=_JOB_ID,
            replace_existing=True,
            max_instances=1,
            name="ShelfSense Analysis Cycle",
        )

        self._scheduler.start()
        logger.info(
            "Scheduler started — running every %d minute(s)", self._interval_min,
        )

        # Push status update to all WebSocket clients
        from core.ws_manager import ws_manager
        ws_manager.broadcast_status_sync()

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        self._scheduler.shutdown(wait=False)
        # Re-create scheduler instance for potential restart
        self._scheduler = BackgroundScheduler(daemon=True)
        logger.info("Scheduler stopped")

        # Push status update to all WebSocket clients
        from core.ws_manager import ws_manager
        ws_manager.broadcast_status_sync()

    def trigger(self) -> dict:
        """Manually trigger one analysis cycle immediately.

        Returns:
            Result summary dict from the cycle.
        """
        logger.info("Manual trigger — running analysis cycle now")
        return self._run_cycle()

    # ── The scheduled job ───────────────────────────────────────────────

    def _run_cycle(self) -> dict:
        """Execute one complete capture → analyse → save cycle.

        Steps:
            1. Capture frame from CameraManager
            2. Save snapshot to captures directory
            3. Load zones from DB
            4. Load reference images
            5. Run ShelfAnalyzer pipeline
            6. Save results to DB
            7. Return summary

        Returns:
            Summary dict with cycle results.
        """
        # Late imports to avoid circular dependencies and to ensure
        # the DB session factory is available at runtime
        import cv2
        from core.camera import camera_manager
        from core.analyzer import ShelfAnalyzer, ZoneDefinition
        from core.product_counter import ProductCounter
        from db.repository import AnalysisRepository, ZoneRepository
        from models.database import SessionLocal

        cycle_start = datetime.now(timezone.utc)
        logger.info("═" * 50)
        logger.info("ANALYSIS CYCLE #%d STARTING", self._cycle_count + 1)
        logger.info("═" * 50)

        try:
            # ── 1. Capture frame ────────────────────────────────────────
            if not camera_manager.connected:
                logger.warning("Camera not connected — attempting reconnect")
                if not camera_manager.reconnect():
                    self._last_status = "failed — camera disconnected"
                    self._last_run = cycle_start
                    logger.error("Cycle aborted — camera unavailable")
                    return {"status": "error", "reason": "camera_disconnected"}

            frame, capture_filename = camera_manager.capture_and_save()
            if frame is None:
                self._last_status = "failed — capture returned empty frame"
                self._last_run = cycle_start
                logger.error("Cycle aborted — empty frame")
                return {"status": "error", "reason": "empty_frame"}

            logger.info("Captured frame → %s", capture_filename)

            # ── 2. Load zones from DB ───────────────────────────────────
            session = SessionLocal()
            try:
                zone_repo = ZoneRepository(session)
                zone_models = zone_repo.get_all()

                if not zone_models:
                    self._last_status = "skipped — no zones configured"
                    self._last_run = cycle_start
                    logger.warning("No zones configured — skipping analysis")
                    return {"status": "skipped", "reason": "no_zones"}

                zone_defs = [
                    ZoneDefinition(
                        zone_id=z.id,
                        zone_name=z.zone_name,
                        product_name=z.product_name,
                        x=z.x,
                        y=z.y,
                        width=z.width,
                        height=z.height,
                        full_threshold=z.full_threshold,
                        low_threshold=z.low_threshold,
                    )
                    for z in zone_models
                ]

                # ── 3. Load reference images ────────────────────────────
                ref_dir = settings.REFERENCES_DIR
                pattern = settings.EMPTY_REFERENCE_GLOB
                ref_paths = sorted(ref_dir.glob(pattern))

                if not ref_paths:
                    self._last_status = "skipped — no reference images"
                    self._last_run = cycle_start
                    logger.warning("No reference images found — skipping")
                    return {"status": "skipped", "reason": "no_references"}

                reference_images = []
                for p in ref_paths:
                    img = cv2.imread(str(p))
                    if img is not None:
                        reference_images.append(img)

                if not reference_images:
                    self._last_status = "skipped — reference images unreadable"
                    self._last_run = cycle_start
                    return {"status": "skipped", "reason": "unreadable_references"}

                # ── 4. Run the CV pipeline ──────────────────────────────
                counter = ProductCounter() if settings.YOLO_ENABLED else None
                analyzer = ShelfAnalyzer(product_counter=counter)
                zone_results = analyzer.analyze_shelf(
                    frame, reference_images, zone_defs,
                )

                # ── 5. Save results to DB ───────────────────────────────
                analysis_repo = AnalysisRepository(session)
                batch = [
                    {
                        "zone_id": r.zone_id,
                        "fill_score": r.fill_score,
                        "status": r.status,
                        "product_count": r.product_count,
                        "image_path": capture_filename,
                        "analyzed_at": r.analyzed_at,
                    }
                    for r in zone_results
                ]
                analysis_repo.save_batch(batch)
                session.commit()

                # ── 6. Build summary ────────────────────────────────────
                full_count = sum(1 for r in zone_results if r.status == "FULL")
                low_count = sum(1 for r in zone_results if r.status == "LOW")
                empty_count = sum(1 for r in zone_results if r.status == "EMPTY")

                summary = {
                    "status": "success",
                    "zones_analyzed": len(zone_results),
                    "full": full_count,
                    "low": low_count,
                    "empty": empty_count,
                    "capture": capture_filename,
                    "analyzed_at": cycle_start.isoformat(),
                }

                self._last_status = (
                    f"success — {len(zone_results)} zones "
                    f"(🟢{full_count} 🟡{low_count} 🔴{empty_count})"
                )
                self._last_run = cycle_start
                self._cycle_count += 1

                logger.info("─" * 50)
                logger.info("CYCLE COMPLETE — %s", self._last_status)
                logger.info("─" * 50)

                # Push results to all WebSocket clients
                from core.ws_manager import ws_manager
                ws_manager.broadcast_status_sync()

                return summary

            finally:
                session.close()

        except Exception as exc:
            self._last_status = f"error — {exc}"
            self._last_run = cycle_start
            logger.exception("Analysis cycle failed: %s", exc)
            return {"status": "error", "reason": str(exc)}

    # ── Status Info ─────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return scheduler status as a JSON-serialisable dict."""
        return {
            "running": self.running,
            "interval_minutes": self._interval_min,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_status": self._last_status,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "cycle_count": self._cycle_count,
        }


# ── Module-level singleton ──────────────────────────────────────────────

analysis_scheduler = AnalysisScheduler()
