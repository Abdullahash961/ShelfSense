"""
ProductCounter — YOLO-based product detection and counting for shelf zones.

Wraps a YOLOv8 model (fine-tuned on SKU-110K) to detect and count individual
products in zone crops.  Designed to run alongside the dissimilarity-based
occupancy pipeline, adding a concrete product count to each zone's analysis.

Usage::

    from core.product_counter import ProductCounter

    counter = ProductCounter()   # loads weights from config
    result  = counter.count_products(zone_crop)
    print(f"Detected {result.count} products")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


# ── Result data classes ─────────────────────────────────────────────────

@dataclass
class Detection:
    """A single detected product bounding box."""
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class ProductCountResult:
    """Result of product counting on a single zone crop."""
    count: int
    detections: list[Detection] = field(default_factory=list)
    confidence_avg: float = 0.0

    def compute_fill_ratio(self, zone_width: int, zone_height: int) -> float:
        """Calculate what fraction of the zone area is covered by detections.

        Uses a binary mask to handle overlapping bounding boxes correctly
        (overlapping regions are only counted once). A small dilation is
        applied to fill narrow gaps between adjacent products on a shelf.

        Args:
            zone_width:  Width of the zone crop in pixels.
            zone_height: Height of the zone crop in pixels.

        Returns:
            Fill ratio in [0.0, 1.0].
        """
        if not self.detections or zone_width <= 0 or zone_height <= 0:
            return 0.0

        # Create a blank mask and "paint" each detection box onto it
        mask = np.zeros((zone_height, zone_width), dtype=np.uint8)
        for det in self.detections:
            x1 = max(0, det.x)
            y1 = max(0, det.y)
            x2 = min(zone_width, det.x + det.width)
            y2 = min(zone_height, det.y + det.height)
            mask[y1:y2, x1:x2] = 1

        # Calculate average product dimensions to scale morphological operations
        avg_w = sum(d.width for d in self.detections) / len(self.detections)
        avg_h = sum(d.height for d in self.detections) / len(self.detections)
        dim = min(avg_w, avg_h)

        # Dilate to fill small gaps between adjacent products
        # (shelf dividers, narrow spaces between tightly packed items)
        dilate_k = max(5, int(dim * 0.25))
        if dilate_k % 2 == 0:
            dilate_k += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_k, dilate_k))
        mask = cv2.dilate(mask, kernel, iterations=1)

        # Close to bridge larger gaps between product clusters
        # (horizontal shelf bars, price tags, shelf dividers)
        close_k = max(7, int(dim * 0.50))
        if close_k % 2 == 0:
            close_k += 1
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_k, close_k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

        filled_pixels = int(mask.sum())
        total_pixels = zone_width * zone_height
        return min(filled_pixels / total_pixels, 1.0)


# ── Main counter class ─────────────────────────────────────────────────

class ProductCounter:
    """Counts products in a zone crop using a YOLOv8 detection model.

    The model is loaded once at construction time and reused across all
    subsequent inference calls.  If the weights file is missing or the
    model fails to load, the counter operates in a degraded mode that
    always returns count=0.

    Args:
        weights_path: Path to the ``.pt`` weights file.  Defaults to the
                      path configured in ``settings.YOLO_WEIGHTS_PATH``.
        confidence:   Minimum detection confidence threshold (0–1).
                      Defaults to ``settings.YOLO_CONFIDENCE``.

    Example::

        counter = ProductCounter()
        result  = counter.count_products(zone_crop)
        print(f"{result.count} products (avg conf {result.confidence_avg:.2f})")
    """

    def __init__(
        self,
        weights_path: Path | str | None = None,
        confidence: float | None = None,
    ) -> None:
        self._weights_path = Path(weights_path or settings.YOLO_WEIGHTS_PATH)
        self._confidence = confidence or settings.YOLO_CONFIDENCE
        self._model = None
        self._available = False

        self._load_model()

    # ── Model loading ──────────────────────────────────────────────────

    def _load_model(self) -> None:
        """Attempt to load the YOLO model from disk."""
        if not self._weights_path.exists():
            logger.warning(
                "YOLO weights not found at %s — product counting disabled",
                self._weights_path,
            )
            return

        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self._weights_path))
            self._available = True
            logger.info(
                "ProductCounter loaded — weights=%s, confidence=%.2f",
                self._weights_path.name, self._confidence,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load YOLO model: %s — product counting disabled",
                exc,
            )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Whether the YOLO model loaded successfully."""
        return self._available

    # ── Inference ──────────────────────────────────────────────────────

    def count_products(self, zone_crop: np.ndarray) -> ProductCountResult:
        """Run YOLO inference on a zone crop and return the product count.

        Args:
            zone_crop: BGR image (numpy array) of a single shelf zone.

        Returns:
            ``ProductCountResult`` with count, detections, and average
            confidence.  Returns count=0 if the model is unavailable or
            the crop is too small.
        """
        if not self._available or self._model is None:
            return ProductCountResult(count=0)

        # Skip degenerate crops
        if zone_crop.shape[0] < 10 or zone_crop.shape[1] < 10:
            logger.debug(
                "Zone crop too small (%dx%d) — skipping YOLO",
                zone_crop.shape[1], zone_crop.shape[0],
            )
            return ProductCountResult(count=0)

        try:
            # Run inference (verbose=False to suppress YOLO's own logging)
            results = self._model(
                zone_crop,
                conf=self._confidence,
                verbose=False,
            )

            if not results or len(results) == 0:
                return ProductCountResult(count=0)

            # Extract detections from the first (and only) result
            result = results[0]
            boxes = result.boxes

            if boxes is None or len(boxes) == 0:
                return ProductCountResult(count=0)

            detections: list[Detection] = []
            confidences: list[float] = []

            for box in boxes:
                # Get bounding box in xyxy format, convert to xywh
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())

                detections.append(Detection(
                    x=int(x1),
                    y=int(y1),
                    width=int(x2 - x1),
                    height=int(y2 - y1),
                    confidence=round(conf, 3),
                ))
                confidences.append(conf)

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            logger.debug(
                "YOLO detected %d products (avg conf=%.3f)",
                len(detections), avg_conf,
            )

            return ProductCountResult(
                count=len(detections),
                detections=detections,
                confidence_avg=round(avg_conf, 3),
            )

        except Exception as exc:
            logger.warning("YOLO inference failed: %s", exc)
            return ProductCountResult(count=0)
