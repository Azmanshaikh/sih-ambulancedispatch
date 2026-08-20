from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.services.corridor import apply_condition_score, display_priority_label, priority_band_of, resolve_conflict
from app.services.fleet import BMSIT, get_ambulances, get_hospital
from app.services.otp import issue_otp, list_active_otps, verify_otp
from app.services.profiles import (
    activate_patient,
    activate_verified_role,
    decide_request,
    list_profiles,
    list_requests,
    mark_otp_pending,
    request_role,
    set_driver_ambulance,
)
from app.services.patient_care import (
    generate_trip_report,
    get_health_profile,
    list_reports_for,
    save_health_profile,
)
from app.services.runtime_state import (
    ack_alert,
    enrich_mission,
    get_latest_mission,
    get_medical_record,
    live_mission_or_none,
    get_mission_for_ambulance,
    get_mission_for_patient,
    list_active_missions,
    list_alerts,
    list_dispatch_cases,
    save_mission,
    set_medical_record,
    set_mission_phase,
    tick_vitals,
    unread_count,
    push_alert,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])

def _with_hospital(profile: dict[str, Any]) -> dict[str, Any]:
    row = dict(profile or {})
    hospital = get_hospital(row.get("hospital_id"))
    row["hospital_name"] = (hospital or {}).get("name")
    return row


class RoleRequestBody(BaseModel):
    requested_role: Literal["driver", "staff", "doctor"]


class ChooseRoleBody(BaseModel):
    role: Literal["patient", "driver", "staff", "doctor"]
    hospital_id: int | None = None


class VerifyOtpBody(BaseModel):
    code: str


class DecideBody(BaseModel):
    approve: bool
    ambulance_id: str | None = None


class RecordBody(BaseModel):
    cardiac: bool = False
    diabetes: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    notes: str = ""


class VisitItem(BaseModel):
    hospital: str = ""
    when: str = ""
    reason: str = ""


class DoctorItem(BaseModel):
    name: str = ""
    specialty: str = ""
    notes: str = ""


class HealthProfileBody(BaseModel):
    allergies: str = ""
    medicines: str = ""
    conditions: str = ""
    cardiac: bool = False
    diabetes: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    visits: list[VisitItem] = []
    doctors: list[DoctorItem] = []
    notes: str = ""


class PhaseBody(BaseModel):
    phase: Literal["pickup", "drop", "complete"]


class ConditionBody(BaseModel):
    score: int


@router.get("/me")
async def me(user: dict[str, Any] = Depends(get_current_user)):
    profile = user.get("profile") or {}
    needs_onboarding = profile.get("status") != "active" or not profile.get("onboarded")
    if profile.get("role") in ("driver", "staff", "doctor", "main_admin") and profile.get("status") == "active":
        needs_onboarding = False
    if profile.get("onboarded") is True and profile.get("status") == "active":
        needs_onboarding = False
    return {
        "status": "success",
        "user": {
            "id": user["id"],
            "email": user["email"],
            **_with_hospital(profile),
            "needs_onboarding": needs_onboarding,
        },
    }


@router.post("/choose-role")
async def choose_role(body: ChooseRoleBody, user: dict[str, Any] = Depends(get_current_user)):
    profile = user.get("profile") or {}
    if profile.get("onboarded") and profile.get("status") == "active":
        return {"status": "success", "user": profile, "otp_sent": False}

    if body.role == "patient":
        row = activate_patient(user["id"])
        row["onboarded"] = True
        return {"status": "success", "user": _with_hospital(row), "otp_sent": False}

    hospital = None
    if body.role == "staff":
        if not body.hospital_id:
            raise HTTPException(status_code=400, detail="Select the hospital you work at")
        hospital = get_hospital(body.hospital_id)
        if not hospital:
            raise HTTPException(status_code=400, detail="Unknown hospital")

    pending = mark_otp_pending(user["id"], body.role, hospital_id=body.hospital_id if body.role == "staff" else None)
    issued = issue_otp(
        user["id"],
        user["email"],
        pending.get("full_name"),
        body.role,
        hospital_id=(hospital or {}).get("id"),
        hospital_name=(hospital or {}).get("name"),
    )
    pending["onboarded"] = False
    emailed_to = issued.get("emailed_to") or ([user["email"]] if user.get("email") else [])
    emailed = bool(issued.get("email_sent"))
    dest = ", ".join(emailed_to) if emailed_to else user.get("email") or "your Gmail"
    hospital_bit = f" at {hospital['name']}" if hospital else ""
    message = (
        f"OTP emailed to {dest}."
        if emailed
        else f"Could not email {dest}. Ask staff to read the code from OTP codes, or check SMTP settings."
    )
    return {
        "status": "success",
        "user": _with_hospital(pending),
        "otp_sent": True,
        "otp_email_sent": emailed,
        "otp_emailed_to": emailed_to,
        "hospital_name": (hospital or {}).get("name"),
        "message": message + (f" You selected{hospital_bit}." if hospital_bit else ""),
    }


@router.post("/verify-otp")
async def confirm_otp(body: VerifyOtpBody, user: dict[str, Any] = Depends(get_current_user)):
    try:
        row = verify_otp(user["id"], body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ambulance_id = None
    hospital_id = None
    if row["requested_role"] in ("driver", "doctor"):
        units = [a for a in get_ambulances() if a.get("status") == "available"]
        ambulance_id = (units[0]["id"] if units else None) or (get_ambulances()[0]["id"] if get_ambulances() else None)
    if row["requested_role"] == "staff":
        hospital_id = row.get("hospital_id") or (user.get("profile") or {}).get("hospital_id")
        if not get_hospital(hospital_id):
            raise HTTPException(status_code=400, detail="Select a hospital before verifying OTP")
    profile = activate_verified_role(user["id"], row["requested_role"], ambulance_id, hospital_id=hospital_id)
    profile["onboarded"] = True
    return {"status": "success", "user": _with_hospital(profile)}


@router.get("/otps")
async def staff_otps(_user: dict[str, Any] = Depends(require_roles("staff"))):
    return {"status": "success", "otps": list_active_otps()}


@router.post("/request-role")
async def ask_role(body: RoleRequestBody, user: dict[str, Any] = Depends(get_current_user)):
    try:
        req = request_role(user["id"], body.requested_role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "request": req}


@router.get("/requests")
async def staff_requests(user: dict[str, Any] = Depends(require_roles("staff"))):
    return {"status": "success", "requests": list_requests("pending"), "profiles": [_with_hospital(p) for p in list_profiles()]}


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
async def live_mission(user: dict[str, Any] = Depends(get_current_user)):
    profile = user.get("profile") or {}
    role = profile.get("role")
    if role in ("driver", "doctor"):
        mission = live_mission_or_none(enrich_mission(get_mission_for_ambulance(profile.get("ambulance_id"))))
    elif role == "patient":
        mission = live_mission_or_none(enrich_mission(get_mission_for_patient(user["id"])))
    elif role == "staff":
        mission = live_mission_or_none(enrich_mission(get_latest_mission()))
    else:
        raise HTTPException(status_code=403, detail="Not allowed for this role")
    if not mission:
        return {"status": "success", "mission": None}
    phase = mission.get("phase") or "pickup"
    pickup_route = mission.get("pickup_route") or []
    drop_route = mission.get("drop_route") or mission.get("route") or []
    eta = mission.get("pickup_minutes") if phase == "pickup" else mission.get("transport_minutes")
    if eta is None:
        eta = mission.get("eta_minutes")
    band = priority_band_of(mission)
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
            "route": pickup_route if phase == "pickup" else drop_route,
            "pickup_route": pickup_route,
            "drop_route": drop_route,
            "eta_minutes": eta,
            "eta_label": f"{eta} min" if eta is not None else None,
            "ambulance_id": mission.get("ambulance_id"),
            "driver_location": mission.get("driver_location"),
            "pickup": mission.get("pickup"),
            "conflict": mission.get("conflict"),
            "priority": mission.get("priority"),
            "priority_label": display_priority_label(mission),
            "condition_score": mission.get("condition_score"),
            "priority_band": band,
            "priority_color": mission.get("priority_color"),
            "report": mission.get("report"),
        },
    }


@router.post("/mission/condition")
async def mission_condition(body: ConditionBody, user: dict[str, Any] = Depends(require_roles("doctor"))):
    try:
        score = int(body.score)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Score must be 1 to 10")
    if score < 1 or score > 10:
        raise HTTPException(status_code=400, detail="Score must be 1 to 10")
    profile = user.get("profile") or {}
    mission = live_mission_or_none(get_mission_for_ambulance(profile.get("ambulance_id")))
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission")
    apply_condition_score(mission, score)
    resolved = resolve_conflict(
        {
            "ambulance_id": mission.get("ambulance_id"),
            "pickup_route": mission.get("pickup_route") or [],
            "route": mission.get("drop_route") or mission.get("route") or [],
        },
        priority=int(mission.get("priority") or 1),
        exclude_ambulance=mission.get("ambulance_id"),
    )
    mission["conflict"] = resolved.get("conflict")
    if resolved.get("pickup_route"):
        mission["pickup_route"] = resolved["pickup_route"]
    if resolved.get("route"):
        mission["route"] = resolved["route"]
        mission["drop_route"] = resolved["route"]
    save_mission(mission)
    band = mission.get("priority_band") or "urgent"
    push_alert(
        "staff",
        "Patient condition updated",
        f"Unit {mission.get('ambulance_id')}: score {score}/10 · {band}",
        ambulance_id=mission.get("ambulance_id"),
        mission_id=mission.get("id"),
    )
    return {
        "status": "success",
        "condition_score": mission.get("condition_score"),
        "priority": mission.get("priority"),
        "priority_band": band,
        "priority_color": mission.get("priority_color"),
        "priority_label": display_priority_label(mission),
        "mission": enrich_mission(mission),
    }


@router.post("/mission/phase")
async def mission_phase(body: PhaseBody, user: dict[str, Any] = Depends(require_roles("driver", "staff"))):
    profile = user.get("profile") or {}
    amb_id = profile.get("ambulance_id") if profile.get("role") == "driver" else None
    mission = set_mission_phase(body.phase, amb_id)
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission")
    report = mission.get("report")
    if body.phase == "complete" and not report:
        report = await generate_trip_report(mission)
        mission["report"] = report
        save_mission(mission)
    return {"status": "success", "phase": mission.get("phase"), "report_id": (report or {}).get("id")}


@router.get("/alerts")
async def get_alerts(user: dict[str, Any] = Depends(get_current_user)):
    role = (user.get("profile") or {}).get("role")
    if role not in ("driver", "staff", "doctor"):
        raise HTTPException(status_code=403, detail="Not allowed for this role")
    amb_id = (user.get("profile") or {}).get("ambulance_id")
    unit = role in ("driver", "doctor")
    alerts = list_alerts(role, amb_id if unit else None)
    if unit and amb_id and not alerts:
        alerts = list_alerts("driver")
    return {"status": "success", "alerts": alerts, "unread": unread_count(role, amb_id if unit else None)}


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str, user: dict[str, Any] = Depends(get_current_user)):
    role = (user.get("profile") or {}).get("role")
    if role not in ("driver", "staff", "doctor"):
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


@router.get("/health-profile")
async def read_health_profile(user: dict[str, Any] = Depends(get_current_user), patient_id: str | None = None):
    role = (user.get("profile") or {}).get("role")
    target = user["id"]
    if patient_id and role == "staff":
        target = patient_id
    elif patient_id and patient_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    return {"status": "success", "profile": get_health_profile(target)}


@router.put("/health-profile")
async def write_health_profile(body: HealthProfileBody, user: dict[str, Any] = Depends(require_roles("patient"))):
    row = save_health_profile(user["id"], body.model_dump())
    set_medical_record(
        user["id"],
        {
            "cardiac": body.cardiac,
            "diabetes": body.diabetes,
            "epilepsy": body.epilepsy,
            "pregnant": body.pregnant,
            "notes": body.notes,
        },
        patient_email=user.get("email"),
    )
    return {"status": "success", "profile": row}


@router.get("/reports")
async def trip_reports(user: dict[str, Any] = Depends(get_current_user)):
    role = (user.get("profile") or {}).get("role")
    if role not in ("staff", "patient"):
        raise HTTPException(status_code=403, detail="Not allowed for this role")
    return {"status": "success", "reports": list_reports_for(user)}


@router.get("/cases")
async def staff_cases(_user: dict[str, Any] = Depends(require_roles("staff"))):
    return {"status": "success", "cases": list_dispatch_cases()}


@router.get("/monitor")
async def staff_monitor(user: dict[str, Any] = Depends(require_roles("staff"))):
    mission = live_mission_or_none(enrich_mission(get_latest_mission()))
    active = [enrich_mission(m) for m in list_active_missions()]
    patient_id = (mission or {}).get("patient_id")
    vitals = tick_vitals(patient_id) if patient_id else {"heart_rate": None, "spo2": None, "source": "none"}
    record = get_medical_record(patient_id) if patient_id else {}
    pickup = (mission or {}).get("pickup") if mission else None
    return {
        "status": "success",
        "unread_alerts": unread_count("staff"),
        "patient": {
            "id": patient_id,
            "name": (mission or {}).get("patient_name"),
            "email": (mission or {}).get("patient_email"),
            "lat": pickup.get("lat") if isinstance(pickup, dict) else None,
            "lng": pickup.get("lng") if isinstance(pickup, dict) else None,
            "address": pickup.get("name") if isinstance(pickup, dict) else None,
            "vitals": vitals,
            "record": record,
            "history": (record or {}).get("history") or [],
        } if mission else None,
        "driver": (mission or {}).get("driver_location"),
        "mission": mission,
        "active_missions": active,
        "health_profile": get_health_profile(patient_id) if patient_id else {},
        "reports": list_reports_for(user),
        "fleet": get_ambulances(),
        "cases": list_dispatch_cases(),
    }
