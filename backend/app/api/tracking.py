import asyncio
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from typing import Any, List
from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.services.dispatch_optimizer import get_optimal_ambulance, get_optimal_hospital_dispatch
from app.services.fleet import (
    BMSIT,
    assign_ambulance,
    get_ambulances,
    get_hospitals,
)
from app.services.runtime_state import save_mission, set_medical_record

router = APIRouter(prefix="/tracking", tags=["Tracking"])


class DispatchRequest(BaseModel):
    incident_lat: float = BMSIT["lat"]
    incident_lng: float = BMSIT["lng"]
    is_raining: bool = False
    address: str = BMSIT["name"]
    patient_name: str | None = None
    cardiac: bool = False
    diabetes: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    notes: str = ""


@router.get("/fleet")
async def live_fleet(_user: dict[str, Any] = Depends(require_roles("staff"))):
    return {
        "status": "success",
        "incident_default": BMSIT,
        "ambulances": get_ambulances(),
        "hospitals": get_hospitals(),
    }


@router.post("/dispatch")
async def simulate_dispatch(req: DispatchRequest, user: dict[str, Any] = Depends(require_roles("staff", "patient"))):
    ambulances = get_ambulances()
    hospitals = get_hospitals()
    result = await asyncio.to_thread(
        get_optimal_hospital_dispatch,
        req.incident_lat,
        req.incident_lng,
        hospitals,
        ambulances,
        req.is_raining,
    )
    if result.get("ambulance_id"):
        assign_ambulance(result["ambulance_id"])

    role = (user.get("profile") or {}).get("role")
    patient_id = user["id"] if role == "patient" else None
    patient_name = req.patient_name or (user.get("profile") or {}).get("full_name") or user.get("email")
    if patient_id:
        set_medical_record(
            patient_id,
            {
                "cardiac": req.cardiac,
                "diabetes": req.diabetes,
                "epilepsy": req.epilepsy,
                "pregnant": req.pregnant,
                "notes": req.notes,
            },
        )

    result["incident"] = {
        "lat": req.incident_lat,
        "lng": req.incident_lng,
        "address": req.address,
    }
    save_mission(
        {
            **result,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "pickup": {"name": req.address, "lat": req.incident_lat, "lng": req.incident_lng},
            "ambulance_id": result.get("ambulance_id"),
            "hospital_name": result.get("hospital_name"),
            "hospital": result.get("hospital"),
            "route": result.get("route") or [],
            "eta_minutes": result.get("eta_minutes"),
        }
    )
    return {"status": "success", "data": result}


@router.post("/dispatch-ambulance")
async def dispatch_nearest_ambulance(req: DispatchRequest, _user: dict[str, Any] = Depends(require_roles("staff"))):
    mock_ambulances = get_ambulances()
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
            await manager.broadcast({"message": data, "type": "echo"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
