from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.services.fleet import BMSIT, get_ambulances
from app.services.profiles import decide_request, list_profiles, list_requests, request_role, set_driver_ambulance
from app.services.runtime_state import (
    enrich_mission,
    get_latest_mission,
    get_medical_record,
    get_mission_for_ambulance,
    set_medical_record,
    tick_vitals,
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
    return {
        "status": "success",
        "mission": {
            "pickup_name": (mission.get("pickup") or {}).get("name") or BMSIT["name"],
            "pickup_person": mission.get("patient_name") or "Assigned patient",
            "heading": (mission.get("pickup") or {}).get("name") or BMSIT["name"],
            "destination": mission.get("hospital_name"),
            "hospital": mission.get("hospital"),
            "route": mission.get("route") or [],
            "eta_minutes": mission.get("eta_minutes"),
            "eta_label": f"{mission.get('eta_minutes')} min" if mission.get("eta_minutes") is not None else None,
            "ambulance_id": mission.get("ambulance_id"),
            "driver_location": mission.get("driver_location"),
            "pickup": mission.get("pickup"),
        },
    }


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
        "patient": {
            "id": patient_id,
            "name": (mission or {}).get("patient_name"),
            "lat": pickup.get("lat") if isinstance(pickup, dict) else BMSIT["lat"],
            "lng": pickup.get("lng") if isinstance(pickup, dict) else BMSIT["lng"],
            "address": pickup.get("name") if isinstance(pickup, dict) else BMSIT["name"],
            "vitals": vitals,
            "record": record,
        },
        "driver": (mission or {}).get("driver_location"),
        "mission": mission,
        "fleet": get_ambulances(),
    }
