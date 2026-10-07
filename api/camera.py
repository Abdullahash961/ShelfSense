"""
Camera & Scheduler Endpoints — Connect camera, stream feed, control scheduler.

Routes:
    GET  /api/camera/status       — camera connection info
    POST /api/camera/connect      — open camera stream
    POST /api/camera/disconnect   — close camera stream
    GET  /api/camera/snapshot     — capture one JPEG frame
    GET  /api/camera/feed         — live MJPEG stream

    GET  /api/scheduler/status    — scheduler state
    POST /api/scheduler/start     — start auto-analysis
    POST /api/scheduler/stop      — stop auto-analysis
    POST /api/scheduler/trigger   — run one cycle immediately
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from core.camera import camera_manager
from core.scheduler import analysis_scheduler
from core.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Camera & Scheduler"])


# ── Request / Response schemas ─────────────────────────────────────────

class CameraConnectRequest(BaseModel):
    """Optional body for POST /api/camera/connect."""
    source: int | str = Field(
        default=0,
        description="Webcam index (int) or RTSP URL (str)",
        examples=[0, "rtsp://192.168.1.100:554/stream"],
    )


class CameraStatusResponse(BaseModel):
    connected: bool
    source: str | None
    resolution: dict | None


class SchedulerStatusResponse(BaseModel):
    running: bool
    interval_minutes: int
    last_run: str | None
    last_status: str
    next_run: str | None
    cycle_count: int


class SchedulerStartRequest(BaseModel):
    """Optional body for POST /api/scheduler/start."""
    interval_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="Override interval in minutes (1–1440)",
    )


# ── Camera Endpoints ───────────────────────────────────────────────────

@router.get(
    "/camera/status",
    response_model=CameraStatusResponse,
    summary="Get camera status",
)
def get_camera_status():
    """Return current camera connection status, source, and resolution."""
    return camera_manager.status()


@router.post(
    "/camera/connect",
    response_model=CameraStatusResponse,
    summary="Connect to camera",
)
def connect_camera(body: CameraConnectRequest | None = None):
    """Open the camera stream (webcam or RTSP)."""
    source = body.source if body else 0

    success = camera_manager.open(source)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not open camera source: {source}",
        )

    # Notify all WebSocket clients about camera connection
    import asyncio
    asyncio.ensure_future(ws_manager.broadcast_status())

    return camera_manager.status()


# ── WebSocket — Real-time status push ──────────────────────────────────

@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    """WebSocket endpoint that pushes scheduler + camera status on change.

    Replaces the old 5-second polling loop. The server broadcasts an update
    whenever:
      - A scheduler cycle completes
      - The scheduler is started / stopped
      - The camera is connected / disconnected

    The client receives JSON messages with the shape::

        {
            "type": "status_update",
            "scheduler": { ... },
            "camera": { ... }
        }
    """
    await ws_manager.connect(websocket)

    # Send current state immediately on connect
    await ws_manager.broadcast_status()

    try:
        # Keep the connection alive — listen for client messages
        # (e.g. ping/pong). The server pushes updates via broadcast.
        while True:
            data = await websocket.receive_text()
            # Client can send "ping" to check liveness
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


@router.post(
    "/camera/disconnect",
    response_model=CameraStatusResponse,
    summary="Disconnect camera",
)
def disconnect_camera():
    """Close the camera stream and release the device."""
    camera_manager.close()

    # Notify all WebSocket clients about camera disconnect
    import asyncio
    asyncio.ensure_future(ws_manager.broadcast_status())

    return camera_manager.status()


@router.get(
    "/camera/snapshot",
    summary="Capture a single frame",
    responses={
        200: {"content": {"image/jpeg": {}}},
        503: {"description": "Camera not connected"},
    },
)
def get_snapshot():
    """Capture one frame from the camera and return as JPEG."""
    if not camera_manager.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera is not connected. Call POST /api/camera/connect first.",
        )

    import cv2

    frame = camera_manager.capture()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to capture frame from camera.",
        )

    # Encode as JPEG
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get(
    "/camera/feed",
    summary="Live MJPEG video stream",
    responses={
        200: {"content": {"multipart/x-mixed-replace": {}}},
        503: {"description": "Camera not connected"},
    },
)
def get_camera_feed():
    """Return a continuous MJPEG stream for the dashboard live-feed.

    Usage in browser::

        <img src="/api/camera/feed" />
    """
    if not camera_manager.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera is not connected. Call POST /api/camera/connect first.",
        )

    return StreamingResponse(
        camera_manager.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Scheduler Endpoints ────────────────────────────────────────────────

@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
)
def get_scheduler_status():
    """Return current scheduler state (running, interval, last/next run)."""
    return analysis_scheduler.status()


@router.post(
    "/scheduler/start",
    response_model=SchedulerStatusResponse,
    summary="Start the analysis scheduler",
)
def start_scheduler(body: SchedulerStartRequest | None = None):
    """Start the periodic analysis scheduler.

    Optionally pass an interval override in the request body.
    """
    interval = body.interval_minutes if body else None

    try:
        analysis_scheduler.start(interval_minutes=interval)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scheduler: {exc}",
        )

    return analysis_scheduler.status()


@router.post(
    "/scheduler/stop",
    response_model=SchedulerStatusResponse,
    summary="Stop the analysis scheduler",
)
def stop_scheduler():
    """Stop the periodic analysis scheduler."""
    analysis_scheduler.stop()
    return analysis_scheduler.status()


@router.post(
    "/scheduler/trigger",
    summary="Trigger one analysis cycle",
)
def trigger_analysis():
    """Manually trigger a single analysis cycle immediately.

    Does not require the scheduler to be running — this is a one-shot
    execution of the capture → analyse → save pipeline.
    """
    if not camera_manager.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera is not connected. Connect the camera first.",
        )

    result = analysis_scheduler.trigger()
    return result
