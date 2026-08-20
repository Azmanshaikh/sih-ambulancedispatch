import asyncio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Any, List
from pydantic import BaseModel

from app.core.security import require_main_admin, require_roles
from app.services.corridor import arm_corridor, corridor_snapshot, mission_priority, resolve_conflict
from app.services.dispatch_optimizer import (
    get_optimal_ambulance,
    get_optimal_hospital_dispatch,
    simulate_custom_route,
)
from app.services.fleet import (
    BMSIT,
    assign_ambulance,
    get_ambulance,
    get_ambulances,
    get_hospitals,
)
from app.services.geocode import geocode_query, reverse_geocode
from app.services.runtime_state import push_alert, save_mission, set_medical_record
from app.services.weather import is_raining_at, weather_snapshot

router = APIRouter(prefix="/tracking", tags=["Tracking"])


class DispatchRequest(BaseModel):
    incident_lat: float = BMSIT["lat"]
    incident_lng: float = BMSIT["lng"]
    is_raining: bool = False
    address: str = BMSIT["name"]
    patient_name: str | None = None
    patient_email: str | None = None
    cardiac: bool = False
    diabetes: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    notes: str = ""
    priority: int | None = None
    analysis: str = ""
    emergency_category: str = "general_medical"
    age_group: str | None = None
    accessibility_need: bool = False


class GeocodeBody(BaseModel):
    query: str = ""
    lat: float | None = None
    lng: float | None = None


class AdminSimulateRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    pickup_address: str = ""
    dest_lat: float
    dest_lng: float
    dest_address: str = ""
    ambulance_id: str
    ambulance_lat: float | None = None
    ambulance_lng: float | None = None
    ambulance_address: str = ""
    is_raining: bool = False
    prefer: str = "fastest"


@router.post("/geocode")
async def lookup_place(body: GeocodeBody, _user: dict[str, Any] = Depends(require_roles("staff", "driver", "doctor", "patient"))):
    if body.query.strip():
        hit = geocode_query(body.query)
        if not hit:
            raise HTTPException(status_code=404, detail="Address not found")
        return {"status": "success", **hit}
    if body.lat is not None and body.lng is not None:
        hit = reverse_geocode(float(body.lat), float(body.lng))
        return {"status": "success", **(hit or {"lat": body.lat, "lng": body.lng, "address": f"{body.lat:.5f}, {body.lng:.5f}"})}
    raise HTTPException(status_code=400, detail="Provide query or lat/lng")


@router.get("/fleet")
async def live_fleet(_user: dict[str, Any] = Depends(require_roles("staff"))):
    return {
        "status": "success",
        "incident_default": BMSIT,
        "ambulances": get_ambulances(),
        "hospitals": get_hospitals(),
    }


@router.get("/corridor")
async def corridor_status(_user: dict[str, Any] = Depends(require_roles("staff", "driver", "doctor"))):
    snap = corridor_snapshot()
    return {"status": "success", **snap}


@router.get("/weather")
async def weather_at(
    lat: float,
    lng: float,
    _user: dict[str, Any] = Depends(require_roles("staff", "patient")),
):
    snap = await asyncio.to_thread(weather_snapshot, lat, lng)
    return {"status": "success", **snap}


@router.post("/dispatch")
async def simulate_dispatch(req: DispatchRequest, user: dict[str, Any] = Depends(require_roles("staff", "patient"))):
    ambulances = get_ambulances()
    hospitals = get_hospitals()
    flags = {
        "cardiac": req.cardiac,
        "diabetes": req.diabetes,
        "epilepsy": req.epilepsy,
        "pregnant": req.pregnant,
    }
    priority = mission_priority(flags, req.priority)
    if req.is_raining:
        is_raining = True
    else:
        is_raining = await asyncio.to_thread(is_raining_at, req.incident_lat, req.incident_lng)
    result = await asyncio.to_thread(
        get_optimal_hospital_dispatch,
        req.incident_lat,
        req.incident_lng,
        hospitals,
        ambulances,
        is_raining,
        req.emergency_category,
        flags,
        req.age_group,
        req.accessibility_need,
    )
    result = resolve_conflict(
        result,
        priority=priority,
        is_raining=is_raining,
        exclude_ambulance=result.get("ambulance_id"),
    )
    if result.get("ambulance_id"):
        pickup = result.get("pickup_route") or []
        drop = result.get("route") or []
        assign_ambulance(
            result["ambulance_id"],
            [(float(p[0]), float(p[1])) for p in pickup if p],
            [(float(p[0]), float(p[1])) for p in drop if p],
        )

    role = (user.get("profile") or {}).get("role")
    patient_id = user["id"] if role == "patient" else None
    patient_name = req.patient_name or (user.get("profile") or {}).get("full_name") or user.get("email")
    patient_email = req.patient_email or user.get("email")
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
            patient_email=patient_email,
        )

    result["incident"] = {
        "lat": req.incident_lat,
        "lng": req.incident_lng,
        "address": req.address,
    }
    result["is_raining"] = is_raining
    mission = save_mission(
        {
            **result,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "pickup": {"name": req.address, "lat": req.incident_lat, "lng": req.incident_lng},
            "ambulance_id": result.get("ambulance_id"),
            "hospital_name": result.get("hospital_name"),
            "hospital": result.get("hospital"),
            "route": result.get("route") or [],
            "pickup_route": result.get("pickup_route") or [],
            "eta_minutes": result.get("eta_minutes"),
            "pickup_minutes": result.get("pickup_minutes"),
            "transport_minutes": result.get("transport_minutes"),
            "phase": "pickup",
            "priority": priority,
            "priority_label": {5: "cardiac", 4: "pregnant", 3: "epilepsy", 2: "diabetes", 1: "standard"}.get(priority, "standard"),
            "emergency_category": result.get("emergency_category"),
            "required_ambulance_types": result.get("required_ambulance_types") or [],
            "assigned_ambulance_type": result.get("assigned_ambulance_type"),
            "assigned_ambulance_type_label": result.get("assigned_ambulance_type_label"),
            "match_status": result.get("match_status"),
            "fallback_reason": result.get("fallback_reason"),
            "accessibility_need": req.accessibility_need,
            "age_group": req.age_group,
            "cardiac": req.cardiac,
            "diabetes": req.diabetes,
            "epilepsy": req.epilepsy,
            "pregnant": req.pregnant,
            "notes": req.notes,
            "analysis": req.analysis,
            "conflict": result.get("conflict") or {"status": "none"},
        }
    )
    hospital_name = result.get("hospital_name") or "hospital"
    unit = result.get("ambulance_id") or "unit"
    push_alert(
        "driver",
        "JOB ASSIGNED",
        f"Pick up {patient_name} at {req.address}, then drop at {hospital_name}. Emergency corridor — shortest path.",
        ambulance_id=result.get("ambulance_id"),
        mission_id=mission.get("id"),
        extra={"pickup": req.address, "drop": hospital_name, "patient_name": patient_name, "ambulance_type": result.get("assigned_ambulance_type"), "match_status": result.get("match_status")},
    )
    push_alert(
        "staff",
        "PATIENT EN ROUTE",
        f"{patient_name} ({patient_email}) is going to {hospital_name} on {unit}.",
        ambulance_id=result.get("ambulance_id"),
        mission_id=mission.get("id"),
        extra={
            "patient_name": patient_name,
            "patient_email": patient_email,
            "hospital_name": hospital_name,
            "ambulance_id": unit,
        },
    )
    conflict = result.get("conflict") or {}
    if conflict.get("reason"):
        push_alert(
            "staff",
            "CORRIDOR CONFLICT",
            conflict["reason"],
            ambulance_id=result.get("ambulance_id"),
            mission_id=mission.get("id"),
            extra=conflict,
        )
    arm_corridor(mission)
    return {"status": "success", "data": result}


@router.post("/dispatch-ambulance")
async def dispatch_nearest_ambulance(req: DispatchRequest, _user: dict[str, Any] = Depends(require_roles("staff"))):
    mock_ambulances = get_ambulances()
    result = get_optimal_ambulance(
        req.incident_lat,
        req.incident_lng,
        mock_ambulances,
        req.emergency_category,
        {"cardiac": req.cardiac, "epilepsy": req.epilepsy, "pregnant": req.pregnant},
        req.age_group,
        req.accessibility_need,
    )
    return {"status": "success", "data": result}


@router.post("/admin/simulate-route")
async def admin_simulate_route(req: AdminSimulateRequest, _user: dict[str, Any] = Depends(require_main_admin())):
    """Dry-run routing for Main Admin — uses the live dispatch engine without creating a mission."""
    ambulance = get_ambulance(req.ambulance_id)
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    sim_ambulance = dict(ambulance)
    if req.ambulance_lat is not None and req.ambulance_lng is not None:
        sim_ambulance["lat"] = req.ambulance_lat
        sim_ambulance["lng"] = req.ambulance_lng

    if req.is_raining:
        is_raining = True
    else:
        is_raining = await asyncio.to_thread(is_raining_at, req.pickup_lat, req.pickup_lng)

    result = await asyncio.to_thread(
        simulate_custom_route,
        sim_ambulance,
        (req.pickup_lat, req.pickup_lng),
        (req.dest_lat, req.dest_lng),
        is_raining=is_raining,
        prefer=req.prefer or "fastest",
    )
    if req.ambulance_lat is not None and req.ambulance_lng is not None:
        result["ambulance_origin"] = {
            "lat": req.ambulance_lat,
            "lng": req.ambulance_lng,
            "address": req.ambulance_address or f"{req.ambulance_lat:.5f}, {req.ambulance_lng:.5f}",
        }
    result["pickup"] = {
        "lat": req.pickup_lat,
        "lng": req.pickup_lng,
        "address": req.pickup_address or f"{req.pickup_lat:.5f}, {req.pickup_lng:.5f}",
    }
    result["destination"] = {
        "lat": req.dest_lat,
        "lng": req.dest_lng,
        "address": req.dest_address or f"{req.dest_lat:.5f}, {req.dest_lng:.5f}",
    }
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
