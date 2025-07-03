from fastapi import WebSocket
from typing import Dict

connected_users: Dict[int, WebSocket] = {}

async def connect_user(user_id: int, websocket: WebSocket):
    await websocket.accept()
    connected_users[user_id] = websocket

def disconnect_user(user_id: int):
    connected_users.pop(user_id, None)

async def forward_signal(to_user_id: int, data: dict):
    receiver_ws = connected_users.get(to_user_id)
    if receiver_ws:
        await receiver_ws.send_json(data)
