"""
ShelfSense — Centralized Configuration

All application settings live here. Values can be overridden by environment
variables or a `.env` file in the project root (via Pydantic BaseSettings).
"""

from pathlib import Path
from pydantic_settings import BaseSettings


# Resolve project root relative to this file
_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Global application settings.

    Attributes are loaded in this priority order:
      1. Environment variables  (e.g. SHELFSENSE_FULL_THRESHOLD=0.60)
      2. Values in a `.env` file at the project root
      3. Defaults defined below
    """

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite:///{(_PROJECT_ROOT / 'data' / 'shelfsense.db').as_posix()}"

    # ── CV Pipeline Thresholds ──────────────────────────────────────────
    FULL_THRESHOLD: float = 0.50   # >= 50% occupancy → FULL
    LOW_THRESHOLD: float = 0.15    # >= 15% occupancy → LOW
    #                                <  15%            → EMPTY

    # ── Image Paths ─────────────────────────────────────────────────────
    REFERENCES_DIR: Path = _PROJECT_ROOT / "data" / "references"
    CAPTURES_DIR: Path = _PROJECT_ROOT / "data" / "captures"
    EMPTY_REFERENCE_GLOB: str = "empty_*.png"  # glob pattern for reference images

    # ── Scheduler ───────────────────────────────────────────────────────
    ANALYSIS_INTERVAL_MINUTES: int = 5

    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── Camera ──────────────────────────────────────────────────────────
    CAMERA_SOURCE: int | str = 0  # 0 = default webcam, or RTSP URL string
    CAMERA_ENABLED: bool = False  # flip to True when camera module is ready
    CAMERA_CAPTURE_WIDTH: int = 1280
    CAMERA_CAPTURE_HEIGHT: int = 720

    # ── Scheduler ─────────────────────────────────────────────────────
    SCHEDULER_AUTO_START: bool = True  # start scheduler on server boot

    # ── YOLO Product Counter ──────────────────────────────────────────────
    YOLO_WEIGHTS_PATH: Path = _PROJECT_ROOT / "weights" / "best.pt"
    YOLO_CONFIDENCE: float = 0.15   # detection confidence threshold
    YOLO_ENABLED: bool = True       # set False to skip product counting

    # ── Notifications (prepared for future integration) ─────────────────
    NOTIFICATIONS_ENABLED: bool = False
    NOTIFICATION_BACKENDS: list[str] = []  # e.g. ["email", "sms", "webhook"]

    model_config = {
        "env_prefix": "SHELFSENSE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Singleton instance — import this everywhere
settings = Settings()
