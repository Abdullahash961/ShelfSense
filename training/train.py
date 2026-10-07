"""
YOLOv8 Fine-Tuning Script — SKU-110K Product Counter

Train YOLOv8 to detect and count products on densely packed retail shelves.
Uses the SKU-110K dataset (single class: "object").

Usage (Google Colab — recommended):
    Run train_colab.ipynb instead (wraps this script with Drive mount + GPU setup)

Usage (local GPU):
    python train.py

The trained model is exported to:
    runs/detect/shelfsense/weights/best.pt
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# ── Ensure ultralytics is available ──────────────────────────────────────
try:
    from ultralytics import YOLO
except ImportError:
    print("Installing ultralytics...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics"])
    from ultralytics import YOLO


def train(
    epochs: int = 50,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "0",
    project: str = "runs/detect",
    name: str = "shelfsense",
    base_model: str = "yolov8n.pt",
    resume: bool = False,
) -> Path:
    """Fine-tune YOLOv8 on SKU-110K.

    Args:
        epochs:     Number of training epochs.
        batch:      Batch size (reduce if OOM).
        imgsz:      Input image size.
        device:     CUDA device ("0", "0,1", or "cpu").
        project:    Output project directory.
        name:       Run name within the project.
        base_model: Pre-trained model checkpoint.
        resume:     Resume from last checkpoint.

    Returns:
        Path to the best trained weights file.
    """
    model = YOLO(base_model)

    # Train — Ultralytics will auto-download SKU-110K when data="SKU-110K"
    results = model.train(
        data="SKU-110K",
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        project=project,
        name=name,
        exist_ok=True,
        resume=resume,
        # Augmentation tuned for dense retail shelves
        mosaic=1.0,         # mosaic augmentation
        mixup=0.1,          # light mixup
        degrees=5.0,        # small rotation (shelves are ~horizontal)
        translate=0.1,      # light translation
        scale=0.3,          # scale jitter
        fliplr=0.5,         # horizontal flip
        flipud=0.0,         # no vertical flip (shelves don't flip)
        hsv_h=0.015,        # hue variation (lighting changes)
        hsv_s=0.5,          # saturation variation
        hsv_v=0.4,          # value/brightness variation
        # Optimization
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=3,
        cos_lr=True,
        patience=10,        # early stopping patience
        # Output
        save=True,
        save_period=10,     # checkpoint every 10 epochs
        plots=True,
        verbose=True,
    )

    best_weights = Path(project) / name / "weights" / "best.pt"
    print(f"\n✅ Training complete! Best model: {best_weights}")

    return best_weights


def evaluate(weights_path: Path, device: str = "0") -> None:
    """Run validation on the trained model and print metrics."""
    model = YOLO(str(weights_path))
    metrics = model.val(data="SKU-110K", device=device)

    print("\n" + "=" * 60)
    print("📊 EVALUATION RESULTS")
    print("=" * 60)
    print(f"  mAP@0.5      : {metrics.box.map50:.4f}")
    print(f"  mAP@0.5:0.95 : {metrics.box.map:.4f}")
    print(f"  Precision     : {metrics.box.mp:.4f}")
    print(f"  Recall        : {metrics.box.mr:.4f}")
    print("=" * 60)


def export_model(weights_path: Path, output_name: str = "yolov8n-shelfsense.pt") -> Path:
    """Copy the best weights to a clean filename for deployment."""
    output = weights_path.parent.parent.parent.parent / output_name
    shutil.copy2(weights_path, output)
    print(f"\n📦 Model exported to: {output}")
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 on SKU-110K for shelf product counting"
    )
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--device", type=str, default="0", help="CUDA device")
    parser.add_argument("--resume", action="store_true", help="Resume training")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate")
    parser.add_argument("--weights", type=str, default=None, help="Weights for eval")
    args = parser.parse_args()

    if args.eval_only:
        weights = Path(args.weights) if args.weights else Path("runs/detect/shelfsense/weights/best.pt")
        evaluate(weights, device=args.device)
        return

    best = train(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        resume=args.resume,
    )

    evaluate(best, device=args.device)
    export_model(best)


if __name__ == "__main__":
    main()
