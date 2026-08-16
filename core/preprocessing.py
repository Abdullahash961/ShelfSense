"""
Image Preprocessing — CLAHE normalization, Gaussian smoothing, ECC alignment.

This module handles all image-level preparation *before* any dissimilarity
computation.  Each method is side-effect-free (returns a new array) and
operates on BGR images unless stated otherwise.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Prepares raw camera frames for downstream comparison.

    Pipeline order (applied by `preprocess`):
        1. Gaussian blur  — suppresses sensor / JPEG noise
        2. CLAHE          — normalizes local brightness (lighting invariance)
        3. ECC alignment  — corrects minor camera drift between captures
    """

    def __init__(
        self,
        blur_ksize: int = 5,
        clahe_clip: float = 2.0,
        clahe_grid: tuple[int, int] = (8, 8),
        ecc_max_iter: int = 50,
        ecc_epsilon: float = 1e-4,
    ) -> None:
        self.blur_ksize = blur_ksize
        self.clahe_clip = clahe_clip
        self.clahe_grid = clahe_grid
        self.ecc_max_iter = ecc_max_iter
        self.ecc_epsilon = ecc_epsilon

        # Pre-build the CLAHE object (reused across all calls)
        self._clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip,
            tileGridSize=self.clahe_grid,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def smooth(self, img: np.ndarray) -> np.ndarray:
        """Apply Gaussian blur to suppress high-frequency noise.

        Args:
            img: BGR image (uint8).

        Returns:
            Smoothed BGR image.
        """
        k = self.blur_ksize
        return cv2.GaussianBlur(img, (k, k), 0)

    def normalize_lighting(self, img: np.ndarray) -> np.ndarray:
        """Apply CLAHE on the L channel in LAB colour space.

        Normalises local brightness caused by overhead lights, shadows, and
        time-of-day changes without distorting colours.

        Args:
            img: BGR image (uint8).

        Returns:
            Lighting-normalised BGR image.
        """
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)

        l_eq = self._clahe.apply(l_ch)

        lab_eq = cv2.merge([l_eq, a_ch, b_ch])
        return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

    def align(self, current: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """Align *current* to *reference* using Enhanced Correlation Coefficient.

        Uses a translational motion model (X/Y shift only) for speed and
        stability.  Falls back to the original image if ECC fails to
        converge (e.g. the images are too different).

        Args:
            current:   BGR image to warp.
            reference: BGR image to align to.

        Returns:
            Aligned BGR image (same shape as *reference*).
        """
        gray_cur = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

        warp_matrix = np.eye(2, 3, dtype=np.float32)
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            self.ecc_max_iter,
            self.ecc_epsilon,
        )
        try:
            _, warp_matrix = cv2.findTransformECC(
                gray_ref,
                gray_cur,
                warp_matrix,
                motionType=cv2.MOTION_TRANSLATION,
                criteria=criteria,
            )
            dx, dy = warp_matrix[0, 2], warp_matrix[1, 2]
            logger.debug("ECC alignment shift: dx=%.2f, dy=%.2f", dx, dy)

            aligned = cv2.warpAffine(
                current,
                warp_matrix,
                (reference.shape[1], reference.shape[0]),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            )
            return aligned
        except cv2.error:
            logger.warning("ECC alignment failed to converge — using original image")
            return current

    def preprocess(
        self,
        current: np.ndarray,
        reference: np.ndarray,
        *,
        skip_align: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run the full preprocessing pipeline on a (current, reference) pair.

        Steps:
            1. Resize *current* to match *reference* if dimensions differ
            2. Gaussian smooth both images
            3. CLAHE lighting normalisation on both images
            4. ECC-align *current* to *reference* (unless *skip_align* is set)

        Args:
            current:    Raw BGR frame from the camera.
            reference:  Empty-shelf reference BGR image.
            skip_align: Skip the ECC alignment step (useful when the full
                        image has already been aligned before cropping).

        Returns:
            (processed_current, processed_reference) ready for dissimilarity.
        """
        # Ensure same dimensions
        if current.shape[:2] != reference.shape[:2]:
            current = cv2.resize(
                current, (reference.shape[1], reference.shape[0])
            )

        # Smooth
        cur_smooth = self.smooth(current)
        ref_smooth = self.smooth(reference)

        # Lighting normalisation
        cur_norm = self.normalize_lighting(cur_smooth)
        ref_norm = self.normalize_lighting(ref_smooth)

        # Align current to reference (skipped when full-image align was done)
        if skip_align:
            return cur_norm, ref_norm

        cur_aligned = self.align(cur_norm, ref_norm)
        return cur_aligned, ref_norm
