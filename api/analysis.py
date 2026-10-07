"""
Analysis Endpoints — Trigger analysis, query status, history, and alerts.

Routes:
    POST /api/analyze                  — upload a shelf photo, run the CV pipeline
    GET  /api/status                   — get latest status of all zones
    GET  /api/zones/{zone_id}/history  — get analysis history for a zone
    GET  /api/alerts                   — get zones that need restocking
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from api.dependencies import get_db
from config import settings
from core.analyzer import ShelfAnalyzer, ZoneDefinition
from core.product_counter import ProductCounter
from db.repository import AnalysisRepository, ZoneRepository
from models.schemas import AnalysisResultResponse, ShelfStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analysis"])

# Maximum upload size: 20 MB
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


# ── Helpers ─────────────────────────────────────────────────────────────

def _load_reference_images() -> list[np.ndarray]:
    """Load all reference images from the configured directory.

    Mirrors the logic in ``main.load_references()`` but without the
    interactive terminal output.
    """
    ref_dir = settings.REFERENCES_DIR
    pattern = settings.EMPTY_REFERENCE_GLOB
    paths = sorted(ref_dir.glob(pattern))

    if not paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No reference images found in {ref_dir}/ "
                f"matching pattern '{pattern}'. "
                f"Upload empty-shelf references via POST /api/references first."
            ),
        )

    images: list[np.ndarray] = []
    for p in paths:
        img = cv2.imread(str(p))
        if img is not None:
            images.append(img)
        else:
            logger.warning("Skipping unreadable reference: %s", p.name)

    if not images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All reference image files were unreadable.",
        )

    # Ensure all images have the same resolution — resize to match the first
    target_shape = images[0].shape[:2]  # (height, width)
    for i in range(1, len(images)):
        if images[i].shape[:2] != target_shape:
            logger.info(
                "Resizing reference image %d from %s to %s",
                i, images[i].shape[:2], target_shape,
            )
            images[i] = cv2.resize(
                images[i],
                (target_shape[1], target_shape[0]),  # cv2.resize takes (w, h)
                interpolation=cv2.INTER_AREA,
            )

    logger.info("Loaded %d reference image(s)", len(images))
    return images


def _zones_to_definitions(zone_models: list) -> list[ZoneDefinition]:
    """Convert ORM ZoneModel objects to ZoneDefinition dataclasses."""
    return [
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


def _build_status_response(
    results: list,
    image_path: str | None = None,
) -> ShelfStatusResponse:
    """Build a ShelfStatusResponse from a list of AnalysisResultModel objects."""
    zones = []
    for r in results:
        zones.append(
            AnalysisResultResponse(
                id=r.id,
                zone_id=r.zone_id,
                zone_name=r.zone.zone_name if r.zone else f"Zone {r.zone_id}",
                product_name=r.zone.product_name if r.zone else "Unknown",
                fill_score=r.fill_score,
                status=r.status,
                product_count=r.product_count,
                image_path=r.image_path,
                analyzed_at=r.analyzed_at,
                x=r.zone.x if r.zone else 0,
                y=r.zone.y if r.zone else 0,
                width=r.zone.width if r.zone else 0,
                height=r.zone.height if r.zone else 0,
            )
        )

    # Summary counts
    summary = {"FULL": 0, "LOW": 0, "EMPTY": 0}
    for z in zones:
        if z.status in summary:
            summary[z.status] += 1

    return ShelfStatusResponse(
        analyzed_at=zones[0].analyzed_at if zones else None,
        image_path=image_path,
        zones=zones,
        summary=summary,
    )


# ── POST /api/analyze ──────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=ShelfStatusResponse,
    summary="Run shelf analysis",
    description="Upload a shelf photo to trigger the full CV pipeline. "
                "Results are saved to the database and returned.",
)
async def analyze_shelf(image: UploadFile, db: Session = Depends(get_db)):
    """Receive a shelf photo, run the CV pipeline, and return results."""

    # ── 1. Validate upload ──────────────────────────────────────────
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Expected an image file, got '{image.content_type}'",
        )

    contents = await image.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image too large ({len(contents)} bytes). Max: {_MAX_UPLOAD_BYTES} bytes.",
        )

    # ── 2. Decode image ─────────────────────────────────────────────
    np_array = np.frombuffer(contents, dtype=np.uint8)
    current_image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if current_image is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not decode the uploaded image.",
        )

    # ── 3. Save capture to disk ─────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    capture_filename = f"capture_{timestamp}.png"
    capture_path = settings.CAPTURES_DIR / capture_filename
    settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(capture_path), current_image)
    logger.info("Saved capture → %s", capture_path)

    # ── 4. Load zones from DB ───────────────────────────────────────
    zone_repo = ZoneRepository(db)
    zone_models = zone_repo.get_all()
    if not zone_models:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No zones defined. Create zones via POST /api/zones first.",
        )

    zone_defs = _zones_to_definitions(zone_models)

    # ── 5. Load references ──────────────────────────────────────────
    reference_images = _load_reference_images()

    # ── 6. Run the CV pipeline ──────────────────────────────────────
    counter = ProductCounter() if settings.YOLO_ENABLED else None
    analyzer = ShelfAnalyzer(product_counter=counter)
    zone_results = analyzer.analyze_shelf(current_image, reference_images, zone_defs)

    # ── 7. Save results to DB ───────────────────────────────────────
    analysis_repo = AnalysisRepository(db)
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
    saved_models = analysis_repo.save_batch(batch)
    db.commit()

    # Refresh to load relationships
    for m in saved_models:
        db.refresh(m)

    # ── 8. Build and return response ────────────────────────────────
    return _build_status_response(saved_models, image_path=capture_filename)


# ── GET /api/status ─────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=ShelfStatusResponse,
    summary="Get current shelf status",
    description="Returns the most recent analysis result for each zone.",
)
def get_status(db: Session = Depends(get_db)):
    """Return the latest analysis result per zone."""
    repo = AnalysisRepository(db)
    latest = repo.get_latest()

    if not latest:
        return ShelfStatusResponse(
            analyzed_at=None,
            image_path=None,
            zones=[],
            summary={"FULL": 0, "LOW": 0, "EMPTY": 0},
        )

    return _build_status_response(latest)


# ── GET /api/zones/{zone_id}/history ────────────────────────────────────

@router.get(
    "/zones/{zone_id}/history",
    response_model=list[AnalysisResultResponse],
    summary="Get analysis history for a zone",
    description="Returns the N most recent analysis results for a specific zone.",
)
def get_zone_history(
    zone_id: int,
    limit: int = Query(default=50, ge=1, le=500, description="Max results to return"),
    db: Session = Depends(get_db),
):
    """Return the analysis history for a specific zone (newest first)."""
    # Verify zone exists
    zone_repo = ZoneRepository(db)
    zone = zone_repo.get_by_id(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )

    analysis_repo = AnalysisRepository(db)
    results = analysis_repo.get_history(zone_id, limit=limit)

    return [
        AnalysisResultResponse(
            id=r.id,
            zone_id=r.zone_id,
            zone_name=zone.zone_name,
            product_name=zone.product_name,
            fill_score=r.fill_score,
            status=r.status,
            product_count=r.product_count,
            image_path=r.image_path,
            analyzed_at=r.analyzed_at,
            x=zone.x,
            y=zone.y,
            width=zone.width,
            height=zone.height,
        )
        for r in results
    ]


# ── GET /api/alerts ─────────────────────────────────────────────────────

@router.get(
    "/alerts",
    response_model=list[AnalysisResultResponse],
    summary="Get restocking alerts",
    description="Returns zones where the latest reading is LOW or EMPTY.",
)
def get_alerts(
    statuses: str = Query(
        default="LOW,EMPTY",
        description="Comma-separated statuses to filter (e.g. LOW,EMPTY)",
    ),
    db: Session = Depends(get_db),
):
    """Return zones that need restocking based on their latest analysis."""
    status_list = [s.strip().upper() for s in statuses.split(",")]

    repo = AnalysisRepository(db)
    alerts = repo.get_alerts(statuses=status_list)

    return [
        AnalysisResultResponse(
            id=r.id,
            zone_id=r.zone_id,
            zone_name=r.zone.zone_name if r.zone else f"Zone {r.zone_id}",
            product_name=r.zone.product_name if r.zone else "Unknown",
            fill_score=r.fill_score,
            status=r.status,
            product_count=r.product_count,
            image_path=r.image_path,
            analyzed_at=r.analyzed_at,
            x=r.zone.x if r.zone else 0,
            y=r.zone.y if r.zone else 0,
            width=r.zone.width if r.zone else 0,
            height=r.zone.height if r.zone else 0,
        )
        for r in alerts
    ]
