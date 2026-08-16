"""
ShelfAnalyzer — Top-level orchestrator for shelf occupancy estimation.

Composes the three pipeline stages:
    ImagePreprocessor → DissimilarityComputer → MorphologyRefiner

and exposes a clean, high-level API for analysing individual zones or an
entire shelf.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np

from config import settings
from core.preprocessing import ImagePreprocessor
from core.dissimilarity import DissimilarityComputer
from core.morphology import MorphologyRefiner

logger = logging.getLogger(__name__)


# ── Result data classes ─────────────────────────────────────────────────

@dataclass
class ZoneDefinition:
    """Describes a single shelf zone (loaded from DB or JSON)."""
    zone_id: int
    zone_name: str
    product_name: str
    x: int
    y: int
    width: int
    height: int
    full_threshold: float = 0.50
    low_threshold: float = 0.15


@dataclass
class ZoneResult:
    """Analysis result for a single zone."""
    zone_id: int
    zone_name: str
    product_name: str
    fill_score: float
    status: str          # "FULL" | "LOW" | "EMPTY"
    x: int
    y: int
    width: int
    height: int
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Main analyser class ────────────────────────────────────────────────

class ShelfAnalyzer:
    """Orchestrates the full shelf-occupancy estimation pipeline.

    The three sub-components are injected via the constructor, defaulting
    to the standard implementations.  This makes it trivial to swap in
    alternative algorithms (e.g. an ML-based dissimilarity module) or to
    mock components in unit tests.

    Example::

        analyzer = ShelfAnalyzer()
        results  = analyzer.analyze_shelf(current_img, ref_img, zones)
        for r in results:
            print(f"{r.zone_name}: {r.status} ({r.fill_score:.1%})")
    """

    def __init__(
        self,
        preprocessor: ImagePreprocessor | None = None,
        dissimilarity: DissimilarityComputer | None = None,
        morphology: MorphologyRefiner | None = None,
        full_threshold: float | None = None,
        low_threshold: float | None = None,
    ) -> None:
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.dissimilarity = dissimilarity or DissimilarityComputer()
        self.morphology = morphology or MorphologyRefiner()
        self.full_threshold = full_threshold or settings.FULL_THRESHOLD
        self.low_threshold = low_threshold or settings.LOW_THRESHOLD

    # ── Classification ──────────────────────────────────────────────────

    def classify(
        self,
        score: float,
        full_threshold: float | None = None,
        low_threshold: float | None = None,
    ) -> str:
        """Classify an occupancy score as FULL, LOW, or EMPTY.

        Per-zone thresholds override the analyser-level defaults when
        provided (allowing different sensitivity per shelf section).

        Args:
            score:          Occupancy ratio in [0, 1].
            full_threshold: Override for FULL cutoff.
            low_threshold:  Override for LOW cutoff.

        Returns:
            ``"FULL"``, ``"LOW"``, or ``"EMPTY"``.
        """
        ft = full_threshold if full_threshold is not None else self.full_threshold
        lt = low_threshold if low_threshold is not None else self.low_threshold

        if score >= ft:
            return "FULL"
        if score >= lt:
            return "LOW"
        return "EMPTY"

    # ── Single-zone analysis ────────────────────────────────────────────

    def analyze_zone(
        self,
        zone_crop: np.ndarray,
        ref_crop: np.ndarray,
        *,
        skip_align: bool = False,
    ) -> float:
        """Run the CV pipeline on a single zone crop and return occupancy.

        Pipeline:
            1. Preprocess (smooth + CLAHE, optionally align) both crops
            2. Compute fused dissimilarity map
            3. Morphological refinement → occupancy ratio

        Args:
            zone_crop:  BGR crop of the zone from the current frame.
            ref_crop:   BGR crop of the same zone from the empty reference.
            skip_align: If True, skip per-zone ECC alignment (e.g. when the
                        full image was already aligned by ``analyze_shelf``).

        Returns:
            Occupancy ratio in [0.0, 1.0].
        """
        # Skip degenerate zones
        if zone_crop.shape[0] < 10 or zone_crop.shape[1] < 10:
            logger.debug("Zone too small (%dx%d), returning 0.0",
                         zone_crop.shape[1], zone_crop.shape[0])
            return 0.0

        # 1. Preprocess (resize + smooth + CLAHE + optional alignment)
        proc_zone, proc_ref = self.preprocessor.preprocess(
            zone_crop, ref_crop, skip_align=skip_align,
        )

        # 2. Dissimilarity
        fused_map = self.dissimilarity.compute_all(proc_zone, proc_ref)

        # 3. Morphology + occupancy
        occupancy = self.morphology.refine(fused_map)

        return occupancy

    # ── Full-shelf analysis ─────────────────────────────────────────────

    def analyze_shelf(
        self,
        current_image: np.ndarray,
        reference_image: np.ndarray,
        zones: list[ZoneDefinition],
    ) -> list[ZoneResult]:
        """Analyse all zones on a shelf and return structured results.

        Steps:
            1. Resize current to match reference if needed
            2. Align current to reference (full-image ECC)
            3. For each zone: crop → analyze_zone (skip per-zone align) → classify
            4. Return list of ``ZoneResult`` objects

        Args:
            current_image:   BGR frame from the camera.
            reference_image: BGR empty-shelf reference.
            zones:           List of ``ZoneDefinition`` objects.

        Returns:
            List of ``ZoneResult``, one per zone.
        """
        # Standardise sizes
        if current_image.shape[:2] != reference_image.shape[:2]:
            logger.info("Resizing current image %s → %s to match reference",
                        current_image.shape[:2], reference_image.shape[:2])
            current_image = cv2.resize(
                current_image,
                (reference_image.shape[1], reference_image.shape[0]),
            )

        # Full-image alignment (corrects camera drift before cropping)
        current_image = self.preprocessor.align(current_image, reference_image)

        timestamp = datetime.now(timezone.utc)
        results: list[ZoneResult] = []

        logger.info("Analyzing %d zones", len(zones))
        for zone in zones:
            x, y, w, h = zone.x, zone.y, zone.width, zone.height

            crop_current = current_image[y : y + h, x : x + w]
            crop_ref = reference_image[y : y + h, x : x + w]

            # skip_align=True because full-image alignment was already done
            score = self.analyze_zone(
                crop_current, crop_ref, skip_align=True,
            )
            status = self.classify(
                score,
                full_threshold=zone.full_threshold,
                low_threshold=zone.low_threshold,
            )

            logger.info("Zone %-12s  score=%.4f  status=%s",
                        zone.zone_name, score, status)

            results.append(
                ZoneResult(
                    zone_id=zone.zone_id,
                    zone_name=zone.zone_name,
                    product_name=zone.product_name,
                    fill_score=round(score, 4),
                    status=status,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    analyzed_at=timestamp,
                )
            )

        return results

    # ── Visualisation helper ────────────────────────────────────────────

    @staticmethod
    def draw_results(
        image: np.ndarray,
        results: list[ZoneResult],
    ) -> np.ndarray:
        """Annotate an image with zone overlays, labels, and fill percentages.

        Args:
            image:   BGR image to annotate (will be copied, not mutated).
            results: Output from ``analyze_shelf``.

        Returns:
            Annotated BGR image.
        """
        img = image.copy()
        colours = {
            "FULL": (0, 200, 0),
            "LOW": (0, 200, 255),
            "EMPTY": (0, 0, 255),
        }

        for r in results:
            x, y, w, h = r.x, r.y, r.width, r.height
            colour = colours.get(r.status, (128, 128, 128))

            # Semi-transparent overlay
            overlay = img.copy()
            cv2.rectangle(overlay, (x, y), (x + w, y + h), colour, -1)
            cv2.addWeighted(overlay, 0.15, img, 0.85, 0, img)

            # Zone boundary
            cv2.rectangle(img, (x, y), (x + w, y + h), colour, 2)

            # Label
            pct = int(r.fill_score * 100)
            label = f"{r.zone_name}: {r.status} ({pct}%)"
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
            )
            cv2.rectangle(
                img, (x, y - th - 12), (x + tw + 8, y), (0, 0, 0), -1
            )
            cv2.putText(
                img, label, (x + 4, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2,
            )

        return img
