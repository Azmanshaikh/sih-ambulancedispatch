from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from pydantic import BaseModel
from app.services.dispatch_optimizer import get_optimal_ambulance

router = APIRouter(prefix="/tracking", tags=["Tracking"])

class DispatchRequest(BaseModel):
    incident_lat: float
    incident_lng: float

@router.post("/dispatch")
async def simulate_dispatch(req: DispatchRequest):
    # Mock some available ambulances for demonstration
    mock_ambulances = [
        {"id": "AMB-101", "location": (28.6139, 77.2090)},
        {"id": "AMB-205", "location": (28.6250, 77.2100)},
        {"id": "AMB-309", "location": (28.6000, 77.1900)},
    ]
    result = get_optimal_ambulance(req.incident_lat, req.incident_lng, mock_ambulances)
    return {"status": "success", "data": result}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or process incoming real-time data
            await manager.broadcast({"message": data, "type": "echo"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
