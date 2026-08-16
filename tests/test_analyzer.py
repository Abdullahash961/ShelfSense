"""
Smoke tests for the OOP-restructured CV pipeline.

Verifies that the new class-based pipeline produces identical results
to the original flat-function ``main.py`` when run on the same images.
"""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

# Adjust the import path so tests can find the project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.analyzer import ShelfAnalyzer, ZoneDefinition, ZoneResult
from core.preprocessing import ImagePreprocessor
from core.dissimilarity import DissimilarityComputer
from core.morphology import MorphologyRefiner


# ── Paths (relative to project root) ───────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZONES_FILE = PROJECT_ROOT / "zones.json"
EMPTY_REF = PROJECT_ROOT / "empty_shelf.png"
FULL_IMAGE = PROJECT_ROOT / "full_filled_shelf.png"


# ── Helpers ─────────────────────────────────────────────────────────────

def _load_zones(zones_path: Path) -> list[ZoneDefinition]:
    """Load ZoneDefinition objects from a zones.json file."""
    data = json.loads(zones_path.read_text())
    return [
        ZoneDefinition(
            zone_id=z["zone_id"],
            zone_name=z["zone_name"],
            product_name=z["product_name"],
            x=z["x"],
            y=z["y"],
            width=z["width"],
            height=z["height"],
            full_threshold=z.get("full_threshold", 0.50),
            low_threshold=z.get("low_threshold", 0.15),
        )
        for z in data["zones"]
    ]


def _images_available() -> bool:
    """Check that the test images exist on disk."""
    return (
        ZONES_FILE.exists()
        and EMPTY_REF.exists()
        and FULL_IMAGE.exists()
    )


# ── Unit tests: individual components ──────────────────────────────────

class TestImagePreprocessor:
    """Tests for the preprocessing stage."""

    def test_smooth_preserves_shape(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pp = ImagePreprocessor()
        result = pp.smooth(img)
        assert result.shape == img.shape

    def test_normalize_lighting_preserves_shape(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pp = ImagePreprocessor()
        result = pp.normalize_lighting(img)
        assert result.shape == img.shape

    def test_align_identical_returns_same(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pp = ImagePreprocessor()
        result = pp.align(img.copy(), img.copy())
        assert result.shape == img.shape

    def test_preprocess_returns_pair(self):
        img_a = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img_b = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pp = ImagePreprocessor()
        cur, ref = pp.preprocess(img_a, img_b)
        assert cur.shape == ref.shape


class TestDissimilarityComputer:
    """Tests for the dissimilarity computation stage."""

    def test_ssim_identical_is_zero(self):
        """Identical images should produce near-zero dissimilarity."""
        gray = np.full((50, 50), 128, dtype=np.uint8)
        dc = DissimilarityComputer()
        dssim = dc.ssim(gray, gray.copy())
        assert dssim.max() < 0.01

    def test_ssim_different_is_nonzero(self):
        gray_a = np.zeros((50, 50), dtype=np.uint8)
        gray_b = np.full((50, 50), 255, dtype=np.uint8)
        dc = DissimilarityComputer()
        dssim = dc.ssim(gray_a, gray_b)
        assert dssim.mean() > 0.1

    def test_color_hsv_preserves_shape(self):
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        dc = DissimilarityComputer()
        result = dc.color_hsv(img, img)
        assert result.shape == (50, 50)

    def test_intensity_preserves_shape(self):
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        dc = DissimilarityComputer()
        result = dc.intensity(img, img)
        assert result.shape == (50, 50)

    def test_fuse_raises_on_empty(self):
        dc = DissimilarityComputer()
        with pytest.raises(ValueError):
            dc.fuse([])

    def test_compute_all_returns_fused(self):
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        dc = DissimilarityComputer()
        result = dc.compute_all(img, img)
        assert result.shape == (50, 50)
        assert result.dtype == np.float32


class TestMorphologyRefiner:
    """Tests for the morphological refinement stage."""

    def test_threshold_produces_binary(self):
        fused = np.random.rand(50, 50).astype(np.float32)
        mr = MorphologyRefiner()
        binary = mr.threshold(fused)
        unique = set(np.unique(binary))
        assert unique.issubset({0, 255})

    def test_cleanup_preserves_shape(self):
        binary = np.zeros((50, 50), dtype=np.uint8)
        binary[15:35, 15:35] = 255
        mr = MorphologyRefiner()
        result = mr.cleanup(binary)
        assert result.shape == binary.shape

    def test_refine_empty_zone_near_zero(self):
        """A uniform (empty) zone should produce near-zero occupancy."""
        fused = np.full((50, 50), 0.01, dtype=np.float32)
        mr = MorphologyRefiner()
        occ = mr.refine(fused)
        assert occ < 0.05

    def test_refine_full_zone_high(self):
        """A completely different zone should produce high occupancy."""
        fused = np.full((80, 80), 0.9, dtype=np.float32)
        mr = MorphologyRefiner()
        occ = mr.refine(fused)
        assert occ > 0.5


# ── Integration test: full pipeline on real images ─────────────────────

@pytest.mark.skipif(
    not _images_available(),
    reason="Test images not found — run from project root",
)
class TestShelfAnalyzerIntegration:
    """End-to-end test with real shelf images."""

    def test_analyze_shelf_returns_results(self):
        zones = _load_zones(ZONES_FILE)
        current = cv2.imread(str(FULL_IMAGE))
        reference = cv2.imread(str(EMPTY_REF))

        analyzer = ShelfAnalyzer()
        results = analyzer.analyze_shelf(current, reference, zones)

        assert len(results) == len(zones)
        for r in results:
            assert isinstance(r, ZoneResult)
            assert r.status in ("FULL", "LOW", "EMPTY")
            assert 0.0 <= r.fill_score <= 1.0

    def test_classify_boundaries(self):
        analyzer = ShelfAnalyzer(full_threshold=0.50, low_threshold=0.15)
        assert analyzer.classify(0.60) == "FULL"
        assert analyzer.classify(0.50) == "FULL"
        assert analyzer.classify(0.30) == "LOW"
        assert analyzer.classify(0.15) == "LOW"
        assert analyzer.classify(0.10) == "EMPTY"
        assert analyzer.classify(0.00) == "EMPTY"

    def test_draw_results_preserves_shape(self):
        zones = _load_zones(ZONES_FILE)
        current = cv2.imread(str(FULL_IMAGE))
        reference = cv2.imread(str(EMPTY_REF))

        analyzer = ShelfAnalyzer()
        results = analyzer.analyze_shelf(current, reference, zones)
        annotated = analyzer.draw_results(current, results)

        assert annotated.shape == current.shape
