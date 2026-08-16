"""
Draw zones on the reference shelf photo and save to zones.json.

Controls:
  Click + drag  → draw a rectangle
  Enter         → save zone (prompts for name + product in terminal)
  u             → undo last zone
  s             → save all zones to zones.json
  q             → quit
"""

import json
from pathlib import Path

import cv2

REFERENCE_IMAGE = "full_filled_shelf.png"
OUTPUT_FILE = "zones.json"

drawing = False
start_x, start_y = 0, 0
current_rect = None
zones = []
next_id = 1


def on_mouse(event, x, y, flags, param):
    global drawing, start_x, start_y, current_rect

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y
        current_rect = None

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_rect = (start_x, start_y, x - start_x, y - start_y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        w, h = x - start_x, y - start_y
        if abs(w) > 10 and abs(h) > 10:
            current_rect = (min(start_x, x), min(start_y, y), abs(w), abs(h))


def draw_overlay(base):
    img = base.copy()
    for z in zones:
        x, y, w, h = z["x"], z["y"], z["width"], z["height"]
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(img, z["zone_name"], (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    if current_rect:
        x, y, w, h = current_rect
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 200, 255), 2)
    return img


def save_zones(reference_image):
    data = {
        "reference_image": reference_image,
        "zones": zones,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(data, indent=2))
    print(f"Saved {len(zones)} zone(s) to {OUTPUT_FILE}")


def main():
    global current_rect, next_id, zones

    img = cv2.imread(REFERENCE_IMAGE)
    if img is None:
        raise FileNotFoundError(f"Could not load {REFERENCE_IMAGE}")

    cv2.namedWindow("Draw zones")
    cv2.setMouseCallback("Draw zones", on_mouse)

    print("Draw a rectangle, then press Enter to name it.")
    print("Keys: Enter=add zone | u=undo | s=save | q=quit")

    while True:
        cv2.imshow("Draw zones", draw_overlay(img))
        key = cv2.waitKey(20) & 0xFF

        if key == ord("q"):
            break

        if key == ord("u") and zones:
            zones.pop()
            next_id -= 1
            print("Removed last zone")

        if key == ord("s"):
            save_zones(REFERENCE_IMAGE)

        if key == 13 and current_rect:  # Enter
            x, y, w, h = current_rect
            name = input("Zone name (e.g. Zone A): ").strip() or f"Zone {next_id}"
            product = input("Product name (e.g. Olpers Milk): ").strip() or "Unassigned"
            zones.append({
                "zone_id": next_id,
                "zone_name": name,
                "product_name": product,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "full_threshold": 0.15,
                "low_threshold": 0.10,
            })
            next_id += 1
            current_rect = None
            print(f"Added {name} → {product}")

    if zones:
        save_zones(REFERENCE_IMAGE)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
