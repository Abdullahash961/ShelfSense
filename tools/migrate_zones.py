"""
Migrate zones.json → SQLite database.

One-time script to import your existing zone definitions from the JSON
file into the new database.  Safe to run multiple times — it skips zones
that already exist (matched by zone_name).

Usage:
    python -m tools.migrate_zones
    python -m tools.migrate_zones --json-path zones.json  (custom path)
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import SessionLocal, ZoneModel, init_db
from db.repository import ZoneRepository


def migrate(json_path: str = "zones.json") -> None:
    """Read zones.json and insert each zone into the database.

    Args:
        json_path: Path to the zones JSON file.
    """
    path = Path(json_path)
    if not path.exists():
        print(f"Error: {json_path} not found.")
        sys.exit(1)

    data = json.loads(path.read_text())
    zones_data = data.get("zones", [])
    reference_image = data.get("reference_image", None)

    if not zones_data:
        print("No zones found in JSON file.")
        return

    # Create tables if they don't exist
    init_db()

    session = SessionLocal()
    repo = ZoneRepository(session)

    try:
        imported = 0
        skipped = 0

        for z in zones_data:
            # Check if this zone already exists (by name)
            existing = (
                session.query(ZoneModel)
                .filter(ZoneModel.zone_name == z["zone_name"])
                .first()
            )

            if existing:
                print(f"  Skipped '{z['zone_name']}' — already exists (id={existing.id})")
                skipped += 1
                continue

            repo.create(
                zone_name=z["zone_name"],
                product_name=z.get("product_name", "Unassigned"),
                x=z["x"],
                y=z["y"],
                width=z["width"],
                height=z["height"],
                full_threshold=z.get("full_threshold", 0.50),
                low_threshold=z.get("low_threshold", 0.15),
                reference_image=reference_image,
            )
            print(f"  Imported '{z['zone_name']}' → {z.get('product_name', 'Unassigned')}")
            imported += 1

        session.commit()
        print(f"\nDone: {imported} imported, {skipped} skipped.")

    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate zones.json → SQLite")
    parser.add_argument(
        "--json-path",
        default="zones.json",
        help="Path to the zones JSON file (default: zones.json)",
    )
    args = parser.parse_args()

    print(f"Migrating zones from {args.json_path} → SQLite database...\n")
    migrate(args.json_path)
