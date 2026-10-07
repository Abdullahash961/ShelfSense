"""
Zone CRUD Endpoints — Create, read, update, and delete shelf zones.

All five endpoints map directly to ``ZoneRepository`` methods.
Routes:
    GET    /api/zones            — list all zones
    GET    /api/zones/{zone_id}  — get a single zone
    POST   /api/zones            — create a new zone
    PUT    /api/zones/{zone_id}  — update an existing zone
    DELETE /api/zones/{zone_id}  — delete a zone
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_db
from db.repository import ZoneRepository
from models.schemas import ZoneCreate, ZoneResponse, ZoneUpdate

router = APIRouter(prefix="/api/zones", tags=["Zones"])


# ── List all zones ──────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ZoneResponse],
    summary="List all zones",
)
def list_zones(db: Session = Depends(get_db)):
    """Return every shelf zone, ordered by ID."""
    repo = ZoneRepository(db)
    return repo.get_all()


# ── Get a single zone ──────────────────────────────────────────────────

@router.get(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Get a single zone",
)
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    """Return a single zone by its primary key."""
    repo = ZoneRepository(db)
    zone = repo.get_by_id(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )
    return zone


# ── Create a new zone ──────────────────────────────────────────────────

@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new zone",
)
def create_zone(body: ZoneCreate, db: Session = Depends(get_db)):
    """Create a new shelf zone with the provided coordinates and metadata."""
    repo = ZoneRepository(db)
    zone = repo.create(**body.model_dump())
    db.commit()
    db.refresh(zone)
    return zone


# ── Update an existing zone ────────────────────────────────────────────

@router.put(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Update a zone",
)
def update_zone(zone_id: int, body: ZoneUpdate, db: Session = Depends(get_db)):
    """Update an existing zone. Only provided fields are changed."""
    repo = ZoneRepository(db)
    zone = repo.update(zone_id, **body.model_dump(exclude_unset=True))
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )
    db.commit()
    db.refresh(zone)
    return zone


# ── Delete a zone ──────────────────────────────────────────────────────

@router.delete(
    "/{zone_id}",
    summary="Delete a zone",
)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Delete a zone and all of its analysis history (cascade)."""
    repo = ZoneRepository(db)
    deleted = repo.delete(zone_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )
    db.commit()
    return {"detail": f"Zone {zone_id} deleted"}
