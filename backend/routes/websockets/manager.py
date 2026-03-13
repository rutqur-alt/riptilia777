from fastapi import WebSocket
from typing import Dict, List

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
