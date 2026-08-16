"""
Pydantic Schemas — Request/response models for the API layer.

These are NOT the database models (those live in ``models.database``).
Pydantic schemas handle:
  - Input validation (what does a valid zone creation request look like?)
  - Output serialization (what shape does the API response have?)
  - Documentation (FastAPI auto-generates Swagger docs from these)
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Zone schemas ───────────────────────────────────────────────────────

class ZoneCreate(BaseModel):
    """Schema for creating a new zone (POST /api/zones)."""
    zone_name: str = Field(..., min_length=1, examples=["Zone A"])
    product_name: str = Field(default="Unassigned", examples=["Olpers Milk"])
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    full_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    low_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    reference_image: str | None = Field(default=None, examples=["empty_shelf.png"])


class ZoneUpdate(BaseModel):
    """Schema for updating a zone (PUT /api/zones/{id}).

    All fields are optional — only provided fields are updated.
    """
    zone_name: str | None = None
    product_name: str | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    full_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    low_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    reference_image: str | None = None


class ZoneResponse(BaseModel):
    """Schema for zone data returned by the API."""
    id: int
    zone_name: str
    product_name: str
    x: int
    y: int
    width: int
    height: int
    full_threshold: float
    low_threshold: float
    reference_image: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Analysis result schemas ────────────────────────────────────────────

class AnalysisResultResponse(BaseModel):
    """Schema for a single zone's analysis result."""
    id: int
    zone_id: int
    zone_name: str
    product_name: str
    fill_score: float
    status: str
    image_path: str | None
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class ShelfStatusResponse(BaseModel):
    """Aggregated response: current status of all zones (latest analysis run)."""
    analyzed_at: datetime | None
    image_path: str | None
    zones: list[AnalysisResultResponse]
    summary: dict[str, int]  # e.g. {"FULL": 2, "LOW": 1, "EMPTY": 1}
