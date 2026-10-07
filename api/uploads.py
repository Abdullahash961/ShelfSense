"""
Reference Image Upload Endpoints — Manage empty-shelf reference images.

Routes:
    POST   /api/references             — upload a new reference image
    GET    /api/references             — list all reference image filenames
    DELETE /api/references/{filename}  — delete a reference image
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, status

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/references", tags=["References"])

# Maximum upload size: 20 MB
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


# ── POST /api/references ───────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a reference image",
    description="Upload an empty-shelf photo to use as a reference for analysis.",
)
async def upload_reference(image: UploadFile):
    """Save an uploaded image to the references directory.

    The file is validated (must be a decodable image) and saved with the
    naming convention ``empty_<timestamp>.png`` so it matches the glob
    pattern used by the analysis pipeline.
    """
    # Validate content type
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

    # Decode to verify it's a valid image
    np_array = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not decode the uploaded file as an image.",
        )

    # Save with timestamped filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"empty_{timestamp}.png"
    save_path = settings.REFERENCES_DIR / filename
    settings.REFERENCES_DIR.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(save_path), img)
    logger.info("Saved reference image → %s", save_path)

    return {
        "filename": filename,
        "message": f"Reference image saved as {filename}",
    }


# ── GET /api/references ────────────────────────────────────────────────

@router.get(
    "",
    summary="List reference images",
    description="Return the filenames of all reference images in the references directory.",
)
def list_references():
    """List all files in the references directory."""
    ref_dir = settings.REFERENCES_DIR

    if not ref_dir.exists():
        return {"references": []}

    files = sorted(
        p.name
        for p in ref_dir.iterdir()
        if p.is_file() and p.name != ".gitkeep"
    )
    return {"references": files}


# ── DELETE /api/references/{filename} ──────────────────────────────────

@router.delete(
    "/{filename}",
    summary="Delete a reference image",
)
def delete_reference(filename: str):
    """Delete a specific reference image by filename."""
    file_path = settings.REFERENCES_DIR / filename

    # Prevent path traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reference image '{filename}' not found",
        )

    file_path.unlink()
    logger.info("Deleted reference image: %s", filename)
    return {"detail": f"Reference image '{filename}' deleted"}
