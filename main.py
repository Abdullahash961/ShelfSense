"""
Analyze shelf zones and report fill level (FULL / LOW / EMPTY).

Uses zones.json (drawn on the reference photo) and compares the current
camera frame against the empty shelf reference using the ShelfAnalyzer
pipeline (preprocessing → dissimilarity → morphological refinement).
"""

import json
import logging
from pathlib import Path

import cv2

from core.analyzer import ShelfAnalyzer, ZoneDefinition

ZONES_FILE = "zones.json"
EMPTY_REFERENCE = "empty_shelf.png"      # The true empty background reference
CURRENT_IMAGE = "full_filled_shelf.png"  # Replace with latest camera capture
OUTPUT_IMAGE = "zone_output.jpg"


def load_zones(zones_path: str) -> list[ZoneDefinition]:
    """Load zone definitions from a JSON file."""
    config = json.loads(Path(zones_path).read_text())
    return [
        ZoneDefinition(
            zone_id=z["zone_id"],
            zone_name=z["zone_name"],
            product_name=z["product_name"],
            x=z["x"],
            y=z["y"],
            width=z["width"],
            height=z["height"],
        )
        for z in config["zones"]
    ]


def main() -> None:
    # Configure logging so pipeline debug/info messages are visible
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load images
    current = cv2.imread(CURRENT_IMAGE)
    if current is None:
        raise FileNotFoundError(f"Could not load current image {CURRENT_IMAGE}")

    empty_ref = cv2.imread(EMPTY_REFERENCE)
    if empty_ref is None:
        raise FileNotFoundError(f"Could not load empty reference {EMPTY_REFERENCE}")

    # Load zones & analyze
    zones = load_zones(ZONES_FILE)
    analyzer = ShelfAnalyzer()
    results = analyzer.analyze_shelf(current, empty_ref, zones)

    # Print summary table
    print(f"\nShelf analysis — {CURRENT_IMAGE}\n")
    print(f"{'Zone':<10} {'Product':<25} {'Score (%)':<12} {'Status'}")
    print("-" * 60)
    for r in results:
        occupancy_percent = f"{round(r.fill_score * 100, 1)}%"
        print(f"{r.zone_name:<10} {r.product_name:<25} {occupancy_percent:<12} {r.status}")

    # Save annotated image
    output = analyzer.draw_results(current, results)
    cv2.imwrite(OUTPUT_IMAGE, output)
    print(f"\nSaved annotated image -> {OUTPUT_IMAGE}")

    # JSON payload (dashboard / database ready)
    payload = [
        {
            "zone_id": r.zone_id,
            "zone_name": r.zone_name,
            "product_name": r.product_name,
            "fill_score": r.fill_score,
            "status": r.status,
            "x": r.x,
            "y": r.y,
            "width": r.width,
            "height": r.height,
        }
        for r in results
    ]
    print("\nDashboard payload:")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
