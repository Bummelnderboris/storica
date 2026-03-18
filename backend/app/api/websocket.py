"""WebSocket endpoint for real-time updates."""

import asyncio
import json
from typing import Optional

import redis.asyncio as redis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.auth import AuthService

router = APIRouter()
settings = get_settings()


class ConnectionManager:
    """Manages WebSocket connections and Redis pub/sub."""

    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
        self._redis: Optional[redis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url)
        return self._redis

    async def connect(self, websocket: WebSocket, project_id: int):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: int):
        """Remove a WebSocket connection."""
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast_to_project(self, project_id: int, message: dict):
        """Send message to all connections for a project."""
        if project_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn, project_id)

    async def publish(self, project_id: int, event_type: str, data: dict):
        """Publish an event to Redis for multi-instance support."""
        r = await self.get_redis()
        message = {
            "project_id": project_id,
            "event_type": event_type,
            "data": data,
        }
        await r.publish(f"project:{project_id}", json.dumps(message))

    async def start_subscriber(self):
        """Start Redis pub/sub subscriber."""
        r = await self.get_redis()
        pubsub = r.pubsub()
        await pubsub.psubscribe("project:*")

        async def listener():
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    data = json.loads(message["data"])
                    project_id = data["project_id"]
                    await self.broadcast_to_project(project_id, {
                        "type": data["event_type"],
                        **data["data"],
                    })

        self._pubsub_task = asyncio.create_task(listener())

    async def stop_subscriber(self):
        """Stop Redis pub/sub subscriber."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass


manager = ConnectionManager()


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: int,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time project updates.

    Requires JWT token as query parameter for authentication.
    """
    # Validate token
    token_data = AuthService.decode_token(token)
    if token_data is None or token_data.type != "access":
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    await manager.connect(websocket, project_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
        })

        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Handle ping/pong for keep-alive
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)


# Helper functions for publishing events from tasks
async def publish_progress(
    project_id: int,
    task_id: int,
    status: str,
    message: str,
    progress_percent: int,
):
    """Publish generation progress event."""
    await manager.publish(project_id, "generation.progress", {
        "task_id": task_id,
        "status": status,
        "message": message,
        "progress_percent": progress_percent,
    })


async def publish_content_ready(
    project_id: int,
    task_id: int,
    content_preview: str,
    word_count: int,
):
    """Publish content ready for approval event."""
    await manager.publish(project_id, "generation.content_ready", {
        "task_id": task_id,
        "content_preview": content_preview,
        "word_count": word_count,
    })


async def publish_completed(
    project_id: int,
    task_id: int,
    next_stage: Optional[str] = None,
):
    """Publish generation completed event."""
    await manager.publish(project_id, "generation.completed", {
        "task_id": task_id,
        "next_stage": next_stage,
    })


async def publish_error(
    project_id: int,
    task_id: int,
    error: str,
    recoverable: bool = True,
):
    """Publish generation error event."""
    await manager.publish(project_id, "generation.error", {
        "task_id": task_id,
        "error": error,
        "recoverable": recoverable,
    })


async def publish_cost_update(
    project_id: int,
    session_tokens: int,
    session_cost_usd: float,
):
    """Publish cost update event."""
    await manager.publish(project_id, "cost.update", {
        "session_tokens": session_tokens,
        "session_cost_usd": session_cost_usd,
    })
