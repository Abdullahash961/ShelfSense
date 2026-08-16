"""
Morphological Refinement — Thresholding + cleanup + border erosion.

Converts a continuous dissimilarity map into a clean binary mask indicating
which pixels are occupied by products, and computes the final occupancy
ratio from that mask.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MorphologyRefiner:
    """Adaptive thresholding, morphological cleanup, and occupancy scoring.

    Parameters control the aggressiveness of noise removal and gap filling.
    Defaults match the V2 pipeline from the original ``main.py``.
    """

    def __init__(
        self,
        min_threshold: int = 30,
        small_kernel_frac: float = 0.03,
        large_kernel_frac: float = 0.08,
        border_frac: float = 0.03,
    ) -> None:
        """
        Args:
            min_threshold:    Otsu floor — if Otsu picks a threshold below
                              this, fall back to this fixed value (0-255).
            small_kernel_frac: Fraction of min(h,w) for the OPEN kernel
                              (speckle noise removal).
            large_kernel_frac: Fraction of min(h,w) for the CLOSE kernel
                              (gap filling inside products).
            border_frac:      Fraction of min(h,w) to erode from zone
                              borders to ignore shelf-edge bleed.
        """
        self.min_threshold = min_threshold
        self.small_kernel_frac = small_kernel_frac
        self.large_kernel_frac = large_kernel_frac
        self.border_frac = border_frac

    # ── Stage A: Thresholding ──────────────────────────────────────────

    def threshold(self, fused_map: np.ndarray) -> np.ndarray:
        """Convert a [0,1] float dissimilarity map to a binary mask via Otsu.

        If Otsu selects a threshold below ``min_threshold`` (meaning the
        zone is almost entirely uniform / empty), falls back to a sensible
        fixed floor to avoid false positives.

        Args:
            fused_map: Float32 dissimilarity map in [0, 1].

        Returns:
            Binary uint8 mask (0 or 255).
        """
        fused_u8 = np.clip(fused_map * 255, 0, 255).astype(np.uint8)

        otsu_val, binary = cv2.threshold(
            fused_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        if otsu_val < self.min_threshold:
            logger.debug(
                "Otsu threshold %.1f below floor %d — using fixed threshold",
                otsu_val, self.min_threshold,
            )
            _, binary = cv2.threshold(
                fused_u8, self.min_threshold, 255, cv2.THRESH_BINARY
            )
        else:
            logger.debug("Otsu threshold selected: %.1f", otsu_val)

        return binary

    # ── Stage B: Two-stage morphological cleanup ───────────────────────

    def cleanup(self, binary: np.ndarray) -> np.ndarray:
        """Remove noise and fill gaps with OPEN → CLOSE morphology.

        Stage 1 (OPEN, small kernel): removes speckle noise and thin shelf
        lines that leak into the zone.

        Stage 2 (CLOSE, large kernel): fills internal gaps within product
        surfaces caused by texture or reflections.

        Args:
            binary: Binary uint8 mask (0 or 255).

        Returns:
            Cleaned binary uint8 mask.
        """
        h, w = binary.shape[:2]
        dim = min(h, w)

        # Small kernel OPEN — remove noise
        small_k = max(3, int(dim * self.small_kernel_frac))
        if small_k % 2 == 0:
            small_k += 1
        small_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (small_k, small_k)
        )
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, small_kernel)

        # Large kernel CLOSE — fill gaps
        large_k = max(5, int(dim * self.large_kernel_frac))
        if large_k % 2 == 0:
            large_k += 1
        large_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (large_k, large_k)
        )
        filled = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, large_kernel)

        return filled

    # ── Stage C: Border erosion ────────────────────────────────────────

    def erode_borders(self, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Zero out pixels near zone edges to ignore shelf-frame bleed.

        Args:
            mask: Binary uint8 mask (0 or 255).

        Returns:
            (refined_mask, border_mask):
                refined_mask — the input with border pixels zeroed.
                border_mask  — the valid-pixel mask used for occupancy calc.
        """
        h, w = mask.shape[:2]
        border_px = max(2, int(min(h, w) * self.border_frac))

        border_mask = np.zeros_like(mask)
        border_mask[border_px:-border_px, border_px:-border_px] = 255

        refined = cv2.bitwise_and(mask, border_mask)
        return refined, border_mask

    # ── Full refinement pipeline ───────────────────────────────────────

    def refine(self, fused_map: np.ndarray) -> float:
        """Run threshold → cleanup → border erosion → occupancy score.

        This is the standard entry point used by ``ShelfAnalyzer``.

        Args:
            fused_map: Float32 dissimilarity map in [0, 1].

        Returns:
            Occupancy ratio in [0.0, 1.0].
        """
        binary = self.threshold(fused_map)
        cleaned = self.cleanup(binary)
        refined, border_mask = self.erode_borders(cleaned)

        valid_pixels = border_mask > 0
        if valid_pixels.sum() == 0:
            return 0.0

        occupancy = float((refined[valid_pixels] > 0).mean())
        logger.debug("Morphology refinement → occupancy=%.4f", occupancy)
        return occupancy
