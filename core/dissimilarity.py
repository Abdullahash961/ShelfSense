"""
Multi-Channel Dissimilarity Computation

Computes pixel-wise dissimilarity maps between a current zone crop and its
empty-shelf reference through three complementary channels:

  1. **SSIM (structural)**  — catches shape / texture changes
  2. **HSV  (chromatic)**   — catches colour changes, shadow-immune
  3. **Intensity (grayscale diff)** — catches brightness changes missed by
     the locally-adaptive SSIM and shadow-immune HSV

All maps are normalised to [0, 1] float32 and fused via a configurable
weighted average (default: 0.5 SSIM + 0.3 HSV + 0.2 Intensity).
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DissimilarityComputer:
    """Compute and fuse multi-channel dissimilarity maps.

    All public methods accept pre-processed images (already smoothed,
    lighting-normalised, and aligned by `ImagePreprocessor`).
    """

    # SSIM constants (based on dynamic range L=255)
    _C1: float = 6.5025    # (0.01 * 255)^2
    _C2: float = 58.5225   # (0.03 * 255)^2

    def __init__(
        self,
        ssim_window_size: int = 11,
        ssim_sigma: float = 1.5,
        hue_weight: float = 0.6,
        sat_weight: float = 0.4,
        fusion_weights: tuple[float, float, float] = (0.5, 0.3, 0.2),
    ) -> None:
        """
        Args:
            ssim_window_size: Size of the Gaussian window for SSIM.
            ssim_sigma:       Sigma of the Gaussian window for SSIM.
            hue_weight:       Weight for hue in HSV chromatic dissimilarity.
            sat_weight:       Weight for saturation in HSV chromatic dissimilarity.
            fusion_weights:   (SSIM, HSV, Intensity) weights for the weighted-
                              average fusion.  Must sum to 1.0.
        """
        self.ssim_window_size = ssim_window_size
        self.ssim_sigma = ssim_sigma
        self.hue_weight = hue_weight
        self.sat_weight = sat_weight
        self.fusion_weights = fusion_weights

    # ── Individual channels ─────────────────────────────────────────────

    def ssim(self, gray_a: np.ndarray, gray_b: np.ndarray) -> np.ndarray:
        """Compute Structural Dissimilarity (DSSIM) between two grayscale images.

        DSSIM = (1 - SSIM) / 2, clipped to [0, 1].

        Args:
            gray_a: Grayscale image (uint8 or float32).
            gray_b: Grayscale image (uint8 or float32), same shape as *gray_a*.

        Returns:
            Float32 dissimilarity map in [0, 1].
        """
        a = gray_a.astype(np.float32)
        b = gray_b.astype(np.float32)

        k = self.ssim_window_size
        s = self.ssim_sigma

        mu_a = cv2.GaussianBlur(a, (k, k), s)
        mu_b = cv2.GaussianBlur(b, (k, k), s)

        mu_a_sq = mu_a * mu_a
        mu_b_sq = mu_b * mu_b
        mu_ab = mu_a * mu_b

        sigma_a_sq = cv2.GaussianBlur(a * a, (k, k), s) - mu_a_sq
        sigma_b_sq = cv2.GaussianBlur(b * b, (k, k), s) - mu_b_sq
        sigma_ab = cv2.GaussianBlur(a * b, (k, k), s) - mu_ab

        numerator = (2 * mu_ab + self._C1) * (2 * sigma_ab + self._C2)
        denominator = (mu_a_sq + mu_b_sq + self._C1) * (
            sigma_a_sq + sigma_b_sq + self._C2
        )
        ssim_map = numerator / denominator

        dssim = np.clip(1.0 - ssim_map, 0, 1)
        return dssim.astype(np.float32)

    def color_hsv(self, img_a: np.ndarray, img_b: np.ndarray) -> np.ndarray:
        """Compute chromatic dissimilarity in HSV space (Hue + Saturation).

        Value channel is intentionally ignored to provide shadow immunity.

        Args:
            img_a: BGR image (uint8).
            img_b: BGR image (uint8), same shape as *img_a*.

        Returns:
            Float32 dissimilarity map in [0, 1].
        """
        hsv_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2HSV)
        hsv_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2HSV)

        ha, sa, _ = cv2.split(hsv_a)
        hb, sb, _ = cv2.split(hsv_b)

        # Circular hue difference (hue wraps at 180 in OpenCV)
        hue_diff = cv2.absdiff(ha, hb).astype(np.float32)
        hue_diff = np.minimum(hue_diff, 180.0 - hue_diff) / 90.0

        # Saturation difference
        sat_diff = cv2.absdiff(sa, sb).astype(np.float32) / 255.0

        # Weighted fusion
        color_dissim = self.hue_weight * hue_diff + self.sat_weight * sat_diff
        return np.clip(color_dissim, 0, 1).astype(np.float32)

    def intensity(self, img_a: np.ndarray, img_b: np.ndarray) -> np.ndarray:
        """Compute normalised absolute grayscale intensity difference.

        Catches cases where SSIM (locally adaptive) and HSV (brightness-
        immune) both miss — e.g. a dark product on a bright shelf with
        similar hue.

        Args:
            img_a: BGR image (uint8).
            img_b: BGR image (uint8), same shape as *img_a*.

        Returns:
            Float32 dissimilarity map in [0, 1].
        """
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return self.intensity_from_gray(gray_a, gray_b)

    def intensity_from_gray(
        self, gray_a: np.ndarray, gray_b: np.ndarray,
    ) -> np.ndarray:
        """Compute normalised absolute grayscale intensity difference.

        Same as :meth:`intensity` but accepts pre-computed grayscale arrays
        to avoid redundant ``cvtColor`` calls.

        Args:
            gray_a: Grayscale image (uint8 or float32).
            gray_b: Grayscale image (uint8 or float32), same shape.

        Returns:
            Float32 dissimilarity map in [0, 1].
        """
        diff = np.abs(gray_a.astype(np.float32) - gray_b.astype(np.float32)) / 255.0
        return diff.astype(np.float32)

    # ── Fusion ──────────────────────────────────────────────────────────────────

    def fuse(
        self,
        maps: list[np.ndarray],
        weights: tuple[float, ...] | None = None,
    ) -> np.ndarray:
        """Fuse multiple dissimilarity maps via weighted average.

        A weighted average is more robust than pixel-wise max because it
        prevents a single noisy channel from dominating the output.

        Args:
            maps:    List of float32 dissimilarity maps, all the same shape.
            weights: Per-map weights (must match length of *maps*).  Falls
                     back to ``self.fusion_weights`` when ``None``.

        Returns:
            Fused float32 map in [0, 1].
        """
        if not maps:
            raise ValueError("At least one dissimilarity map is required.")

        w = weights or self.fusion_weights
        if len(w) != len(maps):
            raise ValueError(
                f"Expected {len(maps)} weights, got {len(w)}"
            )

        result = np.zeros_like(maps[0], dtype=np.float32)
        for m, wi in zip(maps, w):
            result += wi * m
        return np.clip(result, 0, 1)

    # ── Convenience ─────────────────────────────────────────────────────────────

    def compute_all(
        self,
        zone_img: np.ndarray,
        ref_img: np.ndarray,
    ) -> np.ndarray:
        """Compute all three channels and return the fused dissimilarity map.

        This is the standard entry point used by `ShelfAnalyzer`.

        If the zone is too small for the SSIM Gaussian window, SSIM is
        skipped and only HSV + intensity channels are used.

        Args:
            zone_img: Pre-processed BGR zone crop.
            ref_img:  Pre-processed BGR reference crop.

        Returns:
            Fused float32 dissimilarity map in [0, 1].
        """
        gray_zone = cv2.cvtColor(zone_img, cv2.COLOR_BGR2GRAY)
        gray_ref = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

        color_map = self.color_hsv(zone_img, ref_img)
        intensity_map = self.intensity_from_gray(
            gray_zone.astype(np.float32),
            gray_ref.astype(np.float32),
        )

        # Guard: skip SSIM when the zone is smaller than the Gaussian window
        min_dim = min(zone_img.shape[0], zone_img.shape[1])
        if min_dim < self.ssim_window_size:
            logger.debug(
                "Zone too small for SSIM (%dpx < %dpx window), "
                "falling back to HSV + Intensity only",
                min_dim, self.ssim_window_size,
            )
            fused = self.fuse(
                [color_map, intensity_map],
                weights=(0.6, 0.4),
            )
        else:
            dssim_map = self.ssim(gray_zone, gray_ref)

            logger.debug(
                "Dissimilarity stats — SSIM: mean=%.4f max=%.4f  "
                "HSV: mean=%.4f max=%.4f  "
                "Intensity: mean=%.4f max=%.4f",
                dssim_map.mean(), dssim_map.max(),
                color_map.mean(), color_map.max(),
                intensity_map.mean(), intensity_map.max(),
            )

            fused = self.fuse([dssim_map, color_map, intensity_map])

        return fused
