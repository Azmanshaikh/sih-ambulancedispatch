from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.services.fleet import BMSIT, get_ambulances
from app.services.profiles import decide_request, list_profiles, list_requests, request_role, set_driver_ambulance
from app.services.runtime_state import (
    ack_alert,
    enrich_mission,
    get_latest_mission,
    get_medical_record,
    get_mission_for_ambulance,
    list_alerts,
    set_medical_record,
    set_mission_phase,
    tick_vitals,
    unread_count,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


class RoleRequestBody(BaseModel):
    requested_role: Literal["driver", "staff"]


class DecideBody(BaseModel):
    approve: bool
    ambulance_id: str | None = None


class RecordBody(BaseModel):
    cardiac: bool = False
    diabetes: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    notes: str = ""


class PhaseBody(BaseModel):
    phase: Literal["pickup", "drop"]


@router.get("/me")
async def me(user: dict[str, Any] = Depends(get_current_user)):
    return {"status": "success", "user": {"id": user["id"], "email": user["email"], **(user.get("profile") or {})}}


@router.post("/request-role")
async def ask_role(body: RoleRequestBody, user: dict[str, Any] = Depends(get_current_user)):
    try:
        req = request_role(user["id"], body.requested_role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "request": req}


@router.get("/requests")
async def staff_requests(user: dict[str, Any] = Depends(require_roles("staff"))):
    return {"status": "success", "requests": list_requests("pending"), "profiles": list_profiles()}


@router.post("/requests/{request_id}/decide")
async def staff_decide(request_id: str, body: DecideBody, user: dict[str, Any] = Depends(require_roles("staff"))):
    try:
        result = decide_request(request_id, user["id"], body.approve, body.ambulance_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success", **result}


@router.post("/driver/{user_id}/ambulance")
async def bind_ambulance(user_id: str, body: DecideBody, user: dict[str, Any] = Depends(require_roles("staff"))):
    try:
        profile = set_driver_ambulance(user_id, body.ambulance_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success", "profile": profile}


@router.get("/mission")
async def driver_mission(user: dict[str, Any] = Depends(require_roles("driver"))):
    profile = user.get("profile") or {}
    mission = enrich_mission(get_mission_for_ambulance(profile.get("ambulance_id")))
    if not mission:
        mission = enrich_mission(get_latest_mission())
    if not mission:
        return {"status": "success", "mission": None}
    phase = mission.get("phase") or "pickup"
    pickup_route = mission.get("pickup_route") or []
    drop_route = mission.get("drop_route") or mission.get("route") or []
    active_route = pickup_route if phase == "pickup" else drop_route
    eta = mission.get("pickup_minutes") if phase == "pickup" else mission.get("transport_minutes")
    if eta is None:
        eta = mission.get("eta_minutes")
    return {
        "status": "success",
        "mission": {
            "id": mission.get("id"),
            "phase": phase,
            "pickup_name": (mission.get("pickup") or {}).get("name") or BMSIT["name"],
            "pickup_person": mission.get("patient_name") or "Assigned patient",
            "heading": ((mission.get("pickup") or {}).get("name") or BMSIT["name"]) if phase == "pickup" else mission.get("hospital_name"),
            "destination": mission.get("hospital_name"),
            "hospital": mission.get("hospital"),
            "route": active_route,
            "pickup_route": pickup_route,
            "drop_route": drop_route,
            "eta_minutes": eta,
            "eta_label": f"{eta} min" if eta is not None else None,
            "ambulance_id": mission.get("ambulance_id"),
            "driver_location": mission.get("driver_location"),
            "pickup": mission.get("pickup"),
        },
    }


@router.post("/mission/phase")
async def driver_phase(body: PhaseBody, user: dict[str, Any] = Depends(require_roles("driver"))):
    profile = user.get("profile") or {}
    mission = set_mission_phase(body.phase, profile.get("ambulance_id"))
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission")
    return {"status": "success", "phase": mission.get("phase")}


@router.get("/alerts")
async def get_alerts(user: dict[str, Any] = Depends(get_current_user)):
    role = (user.get("profile") or {}).get("role")
    if role not in ("driver", "staff"):
        raise HTTPException(status_code=403, detail="Not allowed for this role")
    amb_id = (user.get("profile") or {}).get("ambulance_id")
    alerts = list_alerts(role, amb_id if role == "driver" else None)
    if role == "driver" and amb_id and not alerts:
        alerts = list_alerts("driver")
    return {"status": "success", "alerts": alerts, "unread": unread_count(role, amb_id if role == "driver" else None)}


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str, user: dict[str, Any] = Depends(get_current_user)):
    role = (user.get("profile") or {}).get("role")
    if role not in ("driver", "staff"):
        raise HTTPException(status_code=403, detail="Not allowed for this role")
    alert = ack_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "alert": alert}


@router.get("/vitals")
async def my_vitals(user: dict[str, Any] = Depends(get_current_user)):
    return {"status": "success", "vitals": tick_vitals(user["id"]), "record": get_medical_record(user["id"])}


@router.post("/records")
async def save_record(body: RecordBody, user: dict[str, Any] = Depends(get_current_user)):
    record = set_medical_record(user["id"], body.model_dump())
    return {"status": "success", "record": record}


@router.get("/monitor")
async def staff_monitor(user: dict[str, Any] = Depends(require_roles("staff"))):
    mission = enrich_mission(get_latest_mission())
    patient_id = (mission or {}).get("patient_id")
    vitals = tick_vitals(patient_id) if patient_id else {"heart_rate": None, "spo2": None, "source": "none"}
    record = get_medical_record(patient_id) if patient_id else {}
    pickup = (mission or {}).get("pickup") or BMSIT
    return {
        "status": "success",
        "unread_alerts": unread_count("staff"),
        "patient": {
            "id": patient_id,
            "name": (mission or {}).get("patient_name"),
            "email": (mission or {}).get("patient_email"),
            "lat": pickup.get("lat") if isinstance(pickup, dict) else BMSIT["lat"],
            "lng": pickup.get("lng") if isinstance(pickup, dict) else BMSIT["lng"],
            "address": pickup.get("name") if isinstance(pickup, dict) else BMSIT["name"],
            "vitals": vitals,
            "record": record,
            "history": (record or {}).get("history") or [],
        },
        "driver": (mission or {}).get("driver_location"),
        "mission": mission,
        "fleet": get_ambulances(),
    }
