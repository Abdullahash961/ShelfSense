"""
Camera Manager — Webcam / RTSP connectivity with thread-safe capture.

Supports:
  - Local webcam via integer index (e.g. 0)
  - IP cameras via RTSP URL string
  - Thread-safe single-frame capture
  - MJPEG streaming for browser live-feed
  - Auto-reconnect on stream failure (3 retries, exponential backoff)

Usage::

    from core.camera import camera_manager

    camera_manager.open(0)               # open default webcam
    frame = camera_manager.capture()      # grab one BGR frame
    camera_manager.close()                # release the device
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from config import settings

logger = logging.getLogger(__name__)

_MAX_RECONNECT_ATTEMPTS = 3
_RECONNECT_BASE_DELAY = 2.0  # seconds — doubles each retry


class CameraManager:
    """Thread-safe camera interface for webcam and RTSP streams.

    Attributes:
        source:     The camera source (int index or RTSP URL string).
        connected:  Whether the camera is currently open and readable.
    """

    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._source: int | str | None = None
        self._resolution: tuple[int, int] | None = None  # (width, height)

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def source(self) -> int | str | None:
        return self._source

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    @property
    def resolution(self) -> tuple[int, int] | None:
        return self._resolution

    # ── Open / Close ────────────────────────────────────────────────────

    def open(self, source: int | str | None = None) -> bool:
        """Open a camera stream.

        Args:
            source: Webcam index (int) or RTSP URL (str).
                    Defaults to ``settings.CAMERA_SOURCE``.

        Returns:
            True if the camera was opened successfully.
        """
        if source is None:
            source = settings.CAMERA_SOURCE

        with self._lock:
            # Close any existing stream first
            if self._cap is not None:
                self._cap.release()
                self._cap = None

            logger.info("Opening camera source: %s", source)
            cap = cv2.VideoCapture(source)

            if not cap.isOpened():
                logger.error("Failed to open camera source: %s", source)
                return False

            # Set resolution if configured
            cap_w = settings.CAMERA_CAPTURE_WIDTH
            cap_h = settings.CAMERA_CAPTURE_HEIGHT
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)

            # Read actual resolution (camera may not support requested)
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._resolution = (actual_w, actual_h)

            self._cap = cap
            self._source = source

            logger.info(
                "Camera opened — source=%s  resolution=%dx%d",
                source, actual_w, actual_h,
            )
            return True

    def close(self) -> None:
        """Release the camera device."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Camera closed (source=%s)", self._source)
            self._source = None
            self._resolution = None

    # ── Frame Capture ───────────────────────────────────────────────────

    def capture(self) -> np.ndarray | None:
        """Grab a single frame from the camera.

        Returns:
            BGR image as ``np.ndarray``, or None if the capture failed.
        """
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                logger.warning("capture() called but camera is not connected")
                return None

            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame from camera")
                return None

            return frame

    def capture_and_save(self) -> tuple[np.ndarray | None, str | None]:
        """Capture a frame and save it to the captures directory.

        Returns:
            Tuple of (BGR frame, filename) or (None, None) on failure.
        """
        frame = self.capture()
        if frame is None:
            return None, None

        # Save to captures directory
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp}.png"
        save_path = settings.CAPTURES_DIR / filename
        settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(str(save_path), frame)
        logger.info("Saved capture → %s", save_path)

        return frame, filename

    # ── Auto-Reconnect ──────────────────────────────────────────────────

    def reconnect(self) -> bool:
        """Attempt to reconnect to the last known source.

        Retries up to 3 times with exponential backoff (2s, 4s, 8s).

        Returns:
            True if reconnection succeeded.
        """
        if self._source is None:
            logger.error("Cannot reconnect — no previous source known")
            return False

        source = self._source
        delay = _RECONNECT_BASE_DELAY

        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            logger.info(
                "Reconnect attempt %d/%d for source=%s (delay=%.1fs)",
                attempt, _MAX_RECONNECT_ATTEMPTS, source, delay,
            )
            time.sleep(delay)

            if self.open(source):
                logger.info("Reconnected successfully on attempt %d", attempt)
                return True

            delay *= 2  # exponential backoff

        logger.error(
            "Failed to reconnect after %d attempts", _MAX_RECONNECT_ATTEMPTS
        )
        return False

    # ── MJPEG Stream Generator ──────────────────────────────────────────

    def generate_mjpeg(self):
        """Yield JPEG-encoded frames for an MJPEG stream.

        This is a synchronous generator intended to be wrapped in a
        ``StreamingResponse`` on the FastAPI side.

        Yields:
            Bytes in multipart/x-mixed-replace format.
        """
        while self.connected:
            frame = self.capture()
            if frame is None:
                # Yield a small delay frame to avoid busy-looping
                time.sleep(0.1)
                continue

            # Encode frame as JPEG
            ret, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            if not ret:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg.tobytes()
                + b"\r\n"
            )

            # ~15 FPS cap to limit CPU usage
            time.sleep(0.066)

    # ── Status Info ─────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return current camera status as a JSON-serialisable dict."""
        return {
            "connected": self.connected,
            "source": str(self._source) if self._source is not None else None,
            "resolution": (
                {"width": self._resolution[0], "height": self._resolution[1]}
                if self._resolution
                else None
            ),
        }


# ── Module-level singleton ──────────────────────────────────────────────

camera_manager = CameraManager()
