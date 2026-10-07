"""
WebSocket Connection Manager — Push scheduler & camera status to dashboards.

Instead of clients polling ``GET /api/scheduler/status`` every 5 seconds,
the server pushes updates over a persistent WebSocket whenever state changes.

Usage::

    from core.ws_manager import ws_manager

    # In a FastAPI WebSocket endpoint:
    await ws_manager.connect(websocket)

    # After a state change (e.g. analysis cycle completes):
    await ws_manager.broadcast_status()
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts status updates."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(
            "WebSocket client connected (total: %d)", len(self._connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (total: %d)", len(self._connections),
        )

    async def broadcast(self, data: dict) -> None:
        """Send a JSON message to all connected clients.

        Silently drops clients that have disconnected.
        """
        message = json.dumps(data)
        stale: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        # Clean up dead connections
        if stale:
            async with self._lock:
                for ws in stale:
                    if ws in self._connections:
                        self._connections.remove(ws)
            logger.debug("Cleaned up %d stale WebSocket(s)", len(stale))

    async def broadcast_status(self) -> None:
        """Gather current scheduler + camera status and broadcast to all clients.

        This is the main method called after any state change:
        - Scheduler cycle completes
        - Scheduler started / stopped
        - Camera connected / disconnected
        """
        from core.camera import camera_manager
        from core.scheduler import analysis_scheduler

        payload = {
            "type": "status_update",
            "scheduler": analysis_scheduler.status(),
            "camera": camera_manager.status(),
        }
        await self.broadcast(payload)

    def broadcast_status_sync(self) -> None:
        """Fire-and-forget broadcast from synchronous code (e.g. scheduler thread).

        Creates a new event loop if needed, or schedules on the running loop.
        """
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context — schedule the coroutine
            loop.create_task(self.broadcast_status())
        except RuntimeError:
            # No running loop (e.g. called from APScheduler thread) —
            # spin up a short-lived loop just for this broadcast
            try:
                asyncio.run(self.broadcast_status())
            except Exception as exc:
                logger.debug("Sync broadcast failed (no clients?): %s", exc)

    @property
    def active_connections(self) -> int:
        return len(self._connections)


# ── Module-level singleton ──────────────────────────────────────────────

ws_manager = ConnectionManager()
