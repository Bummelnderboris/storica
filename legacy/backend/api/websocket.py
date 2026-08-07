"""WebSocket API for real-time updates."""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: int):
        """Connect a client to a project channel."""
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)

    def disconnect(self, websocket: WebSocket, project_id: int):
        """Disconnect a client from a project channel."""
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast(self, project_id: int, message: dict):
        """Broadcast a message to all clients in a project channel."""
        if project_id not in self.active_connections:
            return

        dead_connections = set()
        for connection in self.active_connections[project_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        # Clean up dead connections
        for conn in dead_connections:
            self.active_connections[project_id].discard(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass


manager = ConnectionManager()


@router.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int):
    """WebSocket endpoint for project updates."""
    await manager.connect(websocket, project_id)

    # Send initial connection confirmation
    await manager.send_personal(websocket, {
        "type": "connected",
        "project_id": project_id
    })

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                if message_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})

                elif message_type == "subscribe":
                    # Client subscribing to specific events
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "events": message.get("events", [])
                    })

            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)


async def broadcast_pipeline_event(project_id: int, event_type: str, data: dict):
    """Helper function to broadcast pipeline events."""
    await manager.broadcast(project_id, {
        "type": event_type,
        "data": data
    })


async def broadcast_phase_start(project_id: int, phase: str):
    """Broadcast phase start event."""
    await broadcast_pipeline_event(project_id, "phase_start", {"phase": phase})


async def broadcast_phase_complete(project_id: int, phase: str, output_summary: dict):
    """Broadcast phase complete event."""
    await broadcast_pipeline_event(project_id, "phase_complete", {
        "phase": phase,
        "output_summary": output_summary
    })


async def broadcast_approval_required(project_id: int, phase: str, output_preview: dict):
    """Broadcast approval required event."""
    await broadcast_pipeline_event(project_id, "approval_required", {
        "phase": phase,
        "output_preview": output_preview
    })


async def broadcast_chapter_progress(project_id: int, chapter: int, total: int):
    """Broadcast chapter progress event."""
    await broadcast_pipeline_event(project_id, "chapter_progress", {
        "chapter": chapter,
        "total": total,
        "percent": round((chapter / total) * 100, 1) if total > 0 else 0
    })


async def broadcast_critique_iteration(
    project_id: int,
    chapter: int,
    iteration: int,
    score: float,
    passes: bool
):
    """Broadcast critique iteration event."""
    await broadcast_pipeline_event(project_id, "critique_iteration", {
        "chapter": chapter,
        "iteration": iteration,
        "score": score,
        "passes": passes
    })


async def broadcast_prose_chunk(project_id: int, chapter: int, chunk: str):
    """Broadcast prose generation chunk (streaming)."""
    await broadcast_pipeline_event(project_id, "prose_chunk", {
        "chapter": chapter,
        "chunk": chunk
    })


async def broadcast_error(project_id: int, phase: str, error: str):
    """Broadcast error event."""
    await broadcast_pipeline_event(project_id, "error", {
        "phase": phase,
        "error": error
    })


async def broadcast_complete(project_id: int, cost: dict):
    """Broadcast pipeline complete event."""
    await broadcast_pipeline_event(project_id, "complete", {
        "cost": cost
    })
