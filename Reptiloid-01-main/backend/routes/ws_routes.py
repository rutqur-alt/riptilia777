"""
WebSocket routes for real-time messaging across the platform.
Registered directly on app (not api_router) so paths are /ws/...
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

router = APIRouter()


class UnifiedWSManager:
    """Manages WebSocket connections for trades, conversations, staff chat, etc."""

    def __init__(self):
        # channel -> list of websockets
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, ws: WebSocket, channel: str):
        await ws.accept()
        if channel not in self.connections:
            self.connections[channel] = []
        self.connections[channel].append(ws)

    def disconnect(self, ws: WebSocket, channel: str):
        if channel in self.connections:
            if ws in self.connections[channel]:
                self.connections[channel].remove(ws)
            if not self.connections[channel]:
                del self.connections[channel]

    async def broadcast(self, channel: str, data: dict):
        if channel not in self.connections:
            return
        dead = []
        for ws in self.connections[channel]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)


ws_manager = UnifiedWSManager()


# ==================== TRADE CHAT WEBSOCKET ====================

@router.websocket("/ws/trade/{trade_id}")
async def trade_ws(websocket: WebSocket, trade_id: str):
    """WebSocket for real-time trade chat messages and status updates"""
    channel = f"trade_{trade_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send pings; we just keep connection alive
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)


# ==================== CONVERSATION WEBSOCKET ====================

@router.websocket("/ws/conversation/{conv_id}")
async def conversation_ws(websocket: WebSocket, conv_id: str):
    """WebSocket for real-time unified conversation messages"""
    channel = f"conv_{conv_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)


# ==================== STAFF CHAT WEBSOCKET ====================

@router.websocket("/ws/staff-chat")
async def staff_chat_ws(websocket: WebSocket):
    """WebSocket for real-time staff chat messages"""
    channel = "staff_chat"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)


# ==================== USER NOTIFICATIONS WEBSOCKET ====================

@router.websocket("/ws/user/{user_id}")
async def user_ws(websocket: WebSocket, user_id: str):
    """WebSocket for user-level notifications (new messages, trade updates, etc.)"""
    channel = f"user_{user_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)
