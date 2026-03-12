from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .manager import ws_manager

router = APIRouter()

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
