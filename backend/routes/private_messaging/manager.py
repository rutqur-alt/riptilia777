from fastapi import WebSocket
from typing import Dict, List

class PrivateMessageManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
    
    async def broadcast(self, conversation_id: str, message: dict):
        if conversation_id in self.active_connections:
            for conn in self.active_connections[conversation_id]:
                try:
                    await conn.send_json(message)
                except:
                    pass


private_msg_manager = PrivateMessageManager()
