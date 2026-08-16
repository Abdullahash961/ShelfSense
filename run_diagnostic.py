"""
ShelfSense — CV Pipeline Diagnostic Runner

Runs the full pipeline on all available test images and shows detailed
per-stage output so you can visually inspect what each stage is doing.

Usage:
    python run_diagnostic.py

Outputs:
    - Console: detailed scores + classification table
    - diagnostics/ folder: intermediate images for each zone and stage
"""

import json
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.analyzer import ShelfAnalyzer, ZoneDefinition
from core.preprocessing import ImagePreprocessor
from core.dissimilarity import DissimilarityComputer
from core.morphology import MorphologyRefiner


# ── Configuration ───────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
ZONES_FILE = PROJECT_ROOT / "zones.json"
EMPTY_REF_PATH = PROJECT_ROOT / "empty_shelf.png"
DIAG_DIR = PROJECT_ROOT / "diagnostics"

# Test images: map display name → file path
TEST_IMAGES = {
    "full_filled": PROJECT_ROOT / "full_filled_shelf.png",
    "half_filled": PROJECT_ROOT / "half_filled_shelf.png",
    "half_filled2": PROJECT_ROOT / "half_filled_shelf2.png",
    "sample": PROJECT_ROOT / "sample.png",
}


def load_zones() -> list[ZoneDefinition]:
    """Load zone definitions from zones.json."""
    data = json.loads(ZONES_FILE.read_text())
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


def save_stage_images(
    zone_name: str,
    image_label: str,
    zone_crop: np.ndarray,
    ref_crop: np.ndarray,
    preprocessor: ImagePreprocessor,
    dissimilarity: DissimilarityComputer,
    morphology: MorphologyRefiner,
    output_dir: Path,
) -> dict:
    """Run each pipeline stage individually and save intermediate outputs."""
    prefix = f"{image_label}_{zone_name.replace(' ', '_')}"
    stage_dir = output_dir / image_label
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 0. Raw crops
    cv2.imwrite(str(stage_dir / f"{prefix}_0_crop_current.jpg"), zone_crop)
    cv2.imwrite(str(stage_dir / f"{prefix}_0_crop_reference.jpg"), ref_crop)

    # 1. Preprocessing
    proc_zone, proc_ref = preprocessor.preprocess(
        zone_crop, ref_crop, skip_align=True
    )
    cv2.imwrite(str(stage_dir / f"{prefix}_1_preprocessed_current.jpg"), proc_zone)
    cv2.imwrite(str(stage_dir / f"{prefix}_1_preprocessed_ref.jpg"), proc_ref)

    # 2. Dissimilarity channels (individual)
    gray_zone = cv2.cvtColor(proc_zone, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(proc_ref, cv2.COLOR_BGR2GRAY)

    dssim_map = dissimilarity.ssim(gray_zone, gray_ref)
    hsv_map = dissimilarity.color_hsv(proc_zone, proc_ref)
    intensity_map = dissimilarity.intensity_from_gray(
        gray_zone.astype(np.float32), gray_ref.astype(np.float32)
    )
    fused_map = dissimilarity.compute_all(proc_zone, proc_ref)

    # Save as visible grayscale images (scaled to 0-255)
    cv2.imwrite(str(stage_dir / f"{prefix}_2a_dssim.jpg"),
                (dssim_map * 255).astype(np.uint8))
    cv2.imwrite(str(stage_dir / f"{prefix}_2b_hsv.jpg"),
                (hsv_map * 255).astype(np.uint8))
    cv2.imwrite(str(stage_dir / f"{prefix}_2c_intensity.jpg"),
                (intensity_map * 255).astype(np.uint8))
    cv2.imwrite(str(stage_dir / f"{prefix}_2d_fused.jpg"),
                (fused_map * 255).astype(np.uint8))

    # 3. Morphology stages
    binary = morphology.threshold(fused_map)
    cleaned = morphology.cleanup(binary)
    refined, border_mask = morphology.erode_borders(cleaned)

    cv2.imwrite(str(stage_dir / f"{prefix}_3a_binary.jpg"), binary)
    cv2.imwrite(str(stage_dir / f"{prefix}_3b_cleaned.jpg"), cleaned)
    cv2.imwrite(str(stage_dir / f"{prefix}_3c_refined.jpg"), refined)

    # Compute occupancy from refined mask
    valid_pixels = border_mask > 0
    if valid_pixels.sum() == 0:
        occupancy = 0.0
    else:
        occupancy = float((refined[valid_pixels] > 0).mean())

    return {
        "dssim_mean": float(dssim_map.mean()),
        "dssim_max": float(dssim_map.max()),
        "hsv_mean": float(hsv_map.mean()),
        "hsv_max": float(hsv_map.max()),
        "intensity_mean": float(intensity_map.mean()),
        "intensity_max": float(intensity_map.max()),
        "fused_mean": float(fused_map.mean()),
        "fused_max": float(fused_map.max()),
        "occupancy": occupancy,
    }


def run_diagnostic():
    """Main diagnostic function."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("diagnostic")

    # ── Validate inputs ──────────────────────────────────────────────────
    if not ZONES_FILE.exists():
        print(f"ERROR: zones.json not found at {ZONES_FILE}")
        sys.exit(1)

    if not EMPTY_REF_PATH.exists():
        print(f"ERROR: empty_shelf.png not found at {EMPTY_REF_PATH}")
        sys.exit(1)

    empty_ref = cv2.imread(str(EMPTY_REF_PATH))
    if empty_ref is None:
        print(f"ERROR: Could not decode {EMPTY_REF_PATH}")
        sys.exit(1)

    zones = load_zones()
    log.info("Loaded %d zones from %s", len(zones), ZONES_FILE.name)
    log.info("Reference image shape: %s", empty_ref.shape)

    # Create output directory
    DIAG_DIR.mkdir(exist_ok=True)

    # ── Initialize pipeline components ────────────────────────────────
    preprocessor = ImagePreprocessor()
    dissimilarity = DissimilarityComputer()
    morphology = MorphologyRefiner()
    analyzer = ShelfAnalyzer(
        preprocessor=preprocessor,
        dissimilarity=dissimilarity,
        morphology=morphology,
    )

    # ── Filter available test images ──────────────────────────────────
    available = {k: v for k, v in TEST_IMAGES.items() if v.exists()}
    if not available:
        print("ERROR: No test images found in project root!")
        print("Expected one of:", list(TEST_IMAGES.values()))
        sys.exit(1)

    log.info("Found %d test images: %s", len(available), list(available.keys()))

    # ── Run pipeline on each test image ───────────────────────────────
    for img_label, img_path in available.items():
        print(f"\n{'='*70}")
        print(f"  ANALYZING: {img_path.name}")
        print(f"{'='*70}")

        current = cv2.imread(str(img_path))
        if current is None:
            log.warning("Could not load %s — skipping", img_path)
            continue

        # Resize to match reference if needed
        if current.shape[:2] != empty_ref.shape[:2]:
            log.info("Resizing %s → %s", current.shape[:2], empty_ref.shape[:2])
            current = cv2.resize(
                current, (empty_ref.shape[1], empty_ref.shape[0])
            )

        # Full-image alignment
        aligned = preprocessor.align(current, empty_ref)

        # Run full analysis
        results = analyzer.analyze_shelf(current, empty_ref, zones)

        # Detailed per-zone diagnostics
        print(f"\n  {'Zone':<10} {'Product':<20} {'Score':>8} {'Status':<6}  "
              f"| {'DSSIM':>8} {'HSV':>8} {'Intens':>8} {'Fused':>8}")
        print("  " + "-" * 95)

        for zone, result in zip(zones, results):
            x, y, w, h = zone.x, zone.y, zone.width, zone.height
            crop_cur = aligned[y:y+h, x:x+w]
            crop_ref = empty_ref[y:y+h, x:x+w]

            # Save intermediate stage images
            stats = save_stage_images(
                zone.zone_name, img_label,
                crop_cur, crop_ref,
                preprocessor, dissimilarity, morphology,
                DIAG_DIR,
            )

            pct = f"{result.fill_score * 100:.1f}%"
            print(
                f"  {result.zone_name:<10} {result.product_name:<20} "
                f"{pct:>8} {result.status:<6}  "
                f"| {stats['dssim_mean']:.4f}   {stats['hsv_mean']:.4f}   "
                f"{stats['intensity_mean']:.4f}   {stats['fused_mean']:.4f}"
            )

        # Save annotated output
        output_img = analyzer.draw_results(current, results)
        out_path = DIAG_DIR / f"{img_label}_annotated.jpg"
        cv2.imwrite(str(out_path), output_img)
        print(f"\n  Annotated output saved → {out_path}")

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  DIAGNOSTIC COMPLETE")
    print(f"  Intermediate images saved to: {DIAG_DIR}")
    print(f"  Check the diagnostics/ folder to inspect each pipeline stage!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_diagnostic()
