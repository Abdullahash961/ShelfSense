"""
ShelfSense — FastAPI Application Factory

This is the main entry point for the REST API server.

Start the server with:
    python -m uvicorn app:app --reload

Swagger docs:  http://127.0.0.1:8000/docs
ReDoc:         http://127.0.0.1:8000/redoc
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.analysis import router as analysis_router
from api.camera import router as camera_router
from api.uploads import router as uploads_router
from api.zones import router as zones_router
from config import settings
from core.camera import camera_manager
from core.scheduler import analysis_scheduler
from models.database import init_db

logger = logging.getLogger(__name__)


# ── Lifespan — startup / shutdown events ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run setup on startup, cleanup on shutdown."""
    # Startup: create DB tables if they don't exist
    init_db()
    logger.info("Database initialized — tables ready")

    # Auto-connect camera if enabled
    if settings.CAMERA_ENABLED:
        success = camera_manager.open(settings.CAMERA_SOURCE)
        if success:
            logger.info("Camera auto-connected (source=%s)", settings.CAMERA_SOURCE)
        else:
            logger.warning("Camera auto-connect failed (source=%s)", settings.CAMERA_SOURCE)

    # Auto-start scheduler if enabled and camera is connected
    if settings.SCHEDULER_AUTO_START and camera_manager.connected:
        analysis_scheduler.start()
        logger.info("Scheduler auto-started (interval=%dm)", settings.ANALYSIS_INTERVAL_MINUTES)
    elif settings.SCHEDULER_AUTO_START and not settings.CAMERA_ENABLED:
        logger.info("Scheduler auto-start skipped — camera not enabled")

    yield

    # Shutdown: stop scheduler and release camera
    if analysis_scheduler.running:
        analysis_scheduler.stop()
        logger.info("Scheduler stopped")
    if camera_manager.connected:
        camera_manager.close()
        logger.info("Camera released")
    logger.info("ShelfSense API shutting down")


# ── App instance ────────────────────────────────────────────────────────

app = FastAPI(
    title="ShelfSense API",
    description=(
        "Shelf occupancy monitoring system — REST API.\n\n"
        "Provides endpoints to manage shelf zones, trigger CV-based "
        "occupancy analysis, and query stock levels and restocking alerts."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS (allow dashboard on a different port in Phase 4) ───────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register route modules ─────────────────────────────────────────────

app.include_router(zones_router)
app.include_router(analysis_router)
app.include_router(uploads_router)
app.include_router(camera_router)


# ── Static file serving (shelf captures for dashboard) ─────────────────

settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
settings.REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(settings.CAPTURES_DIR)), name="captures")
app.mount("/references", StaticFiles(directory=str(settings.REFERENCES_DIR)), name="references")


# ── Health check ────────────────────────────────────────────────────────

@app.get("/", tags=["Health"], summary="Health check")
def health_check():
    """Simple health check endpoint to verify the API is running."""
    return {
        "status": "ok",
        "service": "ShelfSense",
        "version": "1.0.0",
    }
