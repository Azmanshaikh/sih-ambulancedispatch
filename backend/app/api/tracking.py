import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Any, List
from pydantic import BaseModel

from app.core.ratelimit import enforce_rate_limit
from app.core.security import require_main_admin, require_roles, user_from_access_token
from app.services.corridor import apply_condition_score, arm_corridor, corridor_snapshot, mission_priority, resolve_conflict
from app.services.dispatch_optimizer import (
    dispatch_requirement,
    get_optimal_ambulance,
    get_optimal_hospital_dispatch,
    nearest_eligible_hospital,
    simulate_custom_route,
    simulate_dual_custom_routes,
)
from app.services.fleet import (
    BMSIT,
    assign_ambulance,
    get_ambulance,
    get_ambulances,
    get_hospital,
    get_hospitals,
    place_ambulance,
)
from app.services.geocode import geocode_query, reverse_geocode
from app.services.runtime_state import push_alert, save_mission, set_medical_record
from app.services.weather import is_raining_at, weather_snapshot

router = APIRouter(prefix="/tracking", tags=["Tracking"])

# Simulation-only patient briefs. Slot 1 is always Azman for the Main Admin lab.
SIM_PATIENTS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Azman",
        "alert": "On blood thinners — high bleeding risk",
        "history": (
            "Azman is on anticoagulant (blood-thinner) therapy because of past blood-clotting / VTE problems."
        ),
        "do_not": [
            "Do not give intramuscular injections (hematoma risk).",
            "Do not give NSAIDs (ibuprofen, diclofenac, aspirin) for pain.",
            "Do not add more anticoagulants or thrombolytics without the receiving doctor.",
            "Do not reverse anticoagulation in the field unless a hospital life-threatening-bleed protocol is in place.",
            "Do not downplay head injury, new weakness, or unexplained hypotension — occult bleeding is more likely.",
        ],
    },
}


def sim_patient_for_slot(slot: int) -> dict[str, Any] | None:
    row = SIM_PATIENTS.get(int(slot))
    return dict(row) if row else None


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


class SimTrafficPoint(BaseModel):
    lat: float
    lng: float
    taps: int = 1


class AdminSimMission2(BaseModel):
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
    hospital_id: int | None = None
    emergency_category: str = "general_medical"
    cardiac: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    previous_drop_sig: str | None = None
    previous_pickup_sig: str | None = None
    danger_rating: int | None = None


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
    push_to_driver: bool = True
    traffic_points: list[SimTrafficPoint] = []
    previous_drop_sig: str | None = None
    previous_pickup_sig: str | None = None
    hospital_id: int | None = None
    emergency_category: str = "general_medical"
    cardiac: bool = False
    epilepsy: bool = False
    pregnant: bool = False
    mission2: AdminSimMission2 | None = None
    danger_rating: int | None = None


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
        "hospitals": [h for h in get_hospitals() if not h.get("simulation")],
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
    role = (user.get("profile") or {}).get("role")
    uid = str(user.get("id") or "")
    if role == "patient":
        enforce_rate_limit(
            f"sos:{uid}",
            max_hits=2,
            window_s=180,
            detail="Emergency SOS rate limit: at most 2 requests every 3 minutes.",
        )
    else:
        enforce_rate_limit(
            f"dispatch:{uid}",
            max_hits=8,
            window_s=60,
            detail="Dispatch rate limit reached.",
        )
    ambulances = get_ambulances()
    hospitals = [h for h in get_hospitals() if not h.get("simulation")]
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


def _sim_unit(ambulance_id: str, lat: float | None, lng: float | None) -> dict[str, Any]:
    ambulance = get_ambulance(ambulance_id)
    if not ambulance:
        raise HTTPException(status_code=404, detail=f"Ambulance not found: {ambulance_id}")
    sim = dict(ambulance)
    if lat is not None and lng is not None:
        sim["lat"] = lat
        sim["lng"] = lng
    return sim


def _sim_destination(hospital_id: int | None, dest_lat: float, dest_lng: float, dest_address: str):
    hospital = get_hospital(hospital_id) if hospital_id is not None else None
    if hospital:
        return hospital, float(hospital["lat"]), float(hospital["lng"]), hospital.get("name") or dest_address
    return None, dest_lat, dest_lng, dest_address


def _critical_sim_hospital(
    pickup: tuple[float, float],
    assigned: dict[str, Any] | None,
    dest_lat: float,
    dest_lng: float,
    dest_address: str,
    rating: int | None,
    category: str,
    flags: dict[str, bool],
    is_raining: bool,
    traffic: list[dict[str, Any]],
):
    """Danger 8–10: replace the assigned drop with the nearest eligible hospital (simulation)."""
    try:
        n = int(rating) if rating is not None else 0
    except (TypeError, ValueError):
        n = 0
    if n < 8:
        return assigned, dest_lat, dest_lng, dest_address, None
    chosen = nearest_eligible_hospital(
        pickup,
        get_hospitals(),
        dispatch_requirement(category, flags),
        is_raining=is_raining,
        traffic_points=traffic or None,
    )
    if not chosen:
        return assigned, dest_lat, dest_lng, dest_address, None
    hospital = chosen["hospital"]
    notice = {
        "danger_rating": n,
        "previous_hospital": (assigned or {}).get("name") or dest_address,
        "previous_hospital_id": (assigned or {}).get("id"),
        "new_hospital": hospital.get("name"),
        "new_hospital_id": hospital.get("id"),
        "match_status": chosen.get("match_status"),
        "reason": f"Danger rating {n}/10 — nearest eligible hospital selected.",
        "changed": (assigned or {}).get("id") != hospital.get("id"),
    }
    if not notice["changed"]:
        notice["reason"] = "Assigned hospital is already the nearest eligible facility."
        return assigned, dest_lat, dest_lng, dest_address, notice
    return (
        hospital,
        float(hospital["lat"]),
        float(hospital["lng"]),
        hospital.get("name") or dest_address,
        notice,
    )


def _annotate_sim_result(
    result: dict[str, Any],
    *,
    pickup_lat: float,
    pickup_lng: float,
    pickup_address: str,
    dest_lat: float,
    dest_lng: float,
    dest_address: str,
    ambulance_lat: float | None,
    ambulance_lng: float | None,
    ambulance_address: str,
) -> dict[str, Any]:
    if ambulance_lat is not None and ambulance_lng is not None:
        result["ambulance_origin"] = {
            "lat": ambulance_lat,
            "lng": ambulance_lng,
            "address": ambulance_address or f"{ambulance_lat:.5f}, {ambulance_lng:.5f}",
        }
    result["pickup"] = {
        "lat": pickup_lat,
        "lng": pickup_lng,
        "address": pickup_address or f"{pickup_lat:.5f}, {pickup_lng:.5f}",
        "name": pickup_address or f"{pickup_lat:.5f}, {pickup_lng:.5f}",
    }
    result["destination"] = {
        "lat": dest_lat,
        "lng": dest_lng,
        "address": dest_address or f"{dest_lat:.5f}, {dest_lng:.5f}",
    }
    return result


def _push_sim_job(
    result: dict[str, Any],
    *,
    ambulance_id: str,
    ambulance_lat: float | None,
    ambulance_lng: float | None,
    pickup_lat: float,
    pickup_lng: float,
    pickup_name: str,
    dest_name: str,
    dest_lat: float,
    dest_lng: float,
    hospital: dict[str, Any] | None,
    emergency_category: str,
    flags: dict[str, bool],
    traffic_points: list[dict[str, Any]],
    slot: int = 1,
) -> dict[str, Any]:
    pickup_path = [(float(p[0]), float(p[1])) for p in (result.get("pickup_route") or []) if p]
    drop_path = [(float(p[0]), float(p[1])) for p in (result.get("route") or []) if p]
    if ambulance_lat is not None and ambulance_lng is not None:
        place_ambulance(ambulance_id, ambulance_lat, ambulance_lng)
    assign_ambulance(ambulance_id, pickup_path, drop_path)
    hospital_payload = hospital or {"name": dest_name, "lat": dest_lat, "lng": dest_lng}
    patient = sim_patient_for_slot(slot) or result.get("patient")
    patient_name = (patient or {}).get("name") or f"Admin simulation {slot}"
    notes = (
        f"{(patient or {}).get('history') or ''} Simulation only — not a live patient.".strip()
        if patient
        else "Pushed from admin route simulation"
    )
    payload = {k: v for k, v in result.items() if k not in ("mission2", "dual")}
    mission = save_mission(
        {
            **payload,
            "simulation": True,
            "patient_id": None,
            "patient_name": patient_name,
            "patient_email": "",
            "patient": patient,
            "doctor_cautions": (patient or {}).get("do_not") or [],
            "pickup": {"name": pickup_name, "lat": pickup_lat, "lng": pickup_lng},
            "ambulance_id": ambulance_id,
            "hospital_name": hospital_payload.get("name") or dest_name,
            "hospital_id": hospital_payload.get("id"),
            "hospital": hospital_payload,
            "emergency_category": result.get("emergency_category") or emergency_category,
            "flags": flags,
            "traffic_points": traffic_points,
            "route": result.get("route") or [],
            "pickup_route": result.get("pickup_route") or [],
            "drop_route": result.get("route") or [],
            "eta_minutes": result.get("eta_minutes"),
            "pickup_minutes": result.get("pickup_minutes"),
            "transport_minutes": result.get("transport_minutes"),
            "phase": "pickup",
            "priority": int(result.get("priority") or 1),
            "priority_label": result.get("priority_label") or "simulation",
            "notes": notes,
            "condition_score": result.get("condition_score"),
            "emergency_reroute": result.get("emergency_reroute"),
        }
    )
    if mission.get("condition_score"):
        apply_condition_score(mission, int(mission["condition_score"]))
        save_mission(mission)
    push_alert(
        "driver",
        "SIMULATION JOB",
        f"Admin simulation {slot}: pick up {patient_name} at {pickup_name}, then drop at {dest_name}.",
        ambulance_id=ambulance_id,
        mission_id=mission.get("id"),
        extra={"pickup": pickup_name, "drop": dest_name, "patient_name": patient_name, "slot": slot},
    )
    push_alert(
        "doctor",
        "SIMULATION JOB",
        f"Admin simulation {slot}: your unit {ambulance_id} only. Pickup {patient_name} at {pickup_name} → {dest_name}.",
        ambulance_id=ambulance_id,
        mission_id=mission.get("id"),
        extra={"pickup": pickup_name, "drop": dest_name, "patient_name": patient_name, "slot": slot},
    )
    arm_corridor(mission)
    result["pushed"] = True
    result["mission_id"] = mission.get("id")
    return result


@router.post("/admin/simulate-route")
async def admin_simulate_route(req: AdminSimulateRequest, _user: dict[str, Any] = Depends(require_main_admin())):
    """Dry-run routing for Main Admin — uses the live dispatch engine without creating a live SOS."""
    traffic = [p.model_dump() for p in req.traffic_points]
    sim_ambulance = _sim_unit(req.ambulance_id, req.ambulance_lat, req.ambulance_lng)
    assigned_hospital, dest_lat, dest_lng, dest_address = _sim_destination(
        req.hospital_id, req.dest_lat, req.dest_lng, req.dest_address
    )
    if req.is_raining:
        is_raining = True
    else:
        is_raining = await asyncio.to_thread(is_raining_at, req.pickup_lat, req.pickup_lng)

    flags_1 = {"cardiac": req.cardiac, "epilepsy": req.epilepsy, "pregnant": req.pregnant}
    assigned_hospital, dest_lat, dest_lng, dest_address, reroute_1 = await asyncio.to_thread(
        _critical_sim_hospital,
        (req.pickup_lat, req.pickup_lng),
        assigned_hospital,
        dest_lat,
        dest_lng,
        dest_address,
        req.danger_rating,
        req.emergency_category,
        flags_1,
        is_raining,
        traffic,
    )
    m2 = req.mission2
    if m2:
        if m2.ambulance_id == req.ambulance_id:
            raise HTTPException(status_code=400, detail="Ambulance 2 must be a different unit from Ambulance 1")
        sim_ambulance_2 = _sim_unit(m2.ambulance_id, m2.ambulance_lat, m2.ambulance_lng)
        hospital_2, dest2_lat, dest2_lng, dest2_address = _sim_destination(
            m2.hospital_id, m2.dest_lat, m2.dest_lng, m2.dest_address
        )
        flags_2 = {"cardiac": m2.cardiac, "epilepsy": m2.epilepsy, "pregnant": m2.pregnant}
        hospital_2, dest2_lat, dest2_lng, dest2_address, reroute_2 = await asyncio.to_thread(
            _critical_sim_hospital,
            (m2.pickup_lat, m2.pickup_lng),
            hospital_2,
            dest2_lat,
            dest2_lng,
            dest2_address,
            m2.danger_rating,
            m2.emergency_category,
            flags_2,
            is_raining,
            traffic,
        )
        result = await asyncio.to_thread(
            simulate_dual_custom_routes,
            sim_ambulance,
            (req.pickup_lat, req.pickup_lng),
            (dest_lat, dest_lng),
            sim_ambulance_2,
            (m2.pickup_lat, m2.pickup_lng),
            (dest2_lat, dest2_lng),
            is_raining=is_raining,
            prefer=req.prefer or "fastest",
            traffic_points=traffic,
            previous_drop_sig=req.previous_drop_sig,
            previous_pickup_sig=req.previous_pickup_sig,
            previous_drop_sig_2=m2.previous_drop_sig,
            previous_pickup_sig_2=m2.previous_pickup_sig,
            hospital_1=assigned_hospital,
            hospital_2=hospital_2,
            emergency_category=req.emergency_category,
            emergency_category_2=m2.emergency_category,
            flags=flags_1,
            flags_2=flags_2,
            hospital_rerouted=bool(reroute_1 and reroute_1.get("changed")),
            hospital_rerouted_2=bool(reroute_2 and reroute_2.get("changed")),
        )
        _annotate_sim_result(
            result,
            pickup_lat=req.pickup_lat,
            pickup_lng=req.pickup_lng,
            pickup_address=req.pickup_address,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            dest_address=dest_address,
            ambulance_lat=req.ambulance_lat,
            ambulance_lng=req.ambulance_lng,
            ambulance_address=req.ambulance_address,
        )
        mission2 = result.get("mission2") or {}
        _annotate_sim_result(
            mission2,
            pickup_lat=m2.pickup_lat,
            pickup_lng=m2.pickup_lng,
            pickup_address=m2.pickup_address,
            dest_lat=dest2_lat,
            dest_lng=dest2_lng,
            dest_address=dest2_address,
            ambulance_lat=m2.ambulance_lat,
            ambulance_lng=m2.ambulance_lng,
            ambulance_address=m2.ambulance_address,
        )
        result["mission2"] = mission2
        result["patient"] = sim_patient_for_slot(1)
        if req.danger_rating is not None:
            result["condition_score"] = int(req.danger_rating)
        if m2.danger_rating is not None:
            mission2["condition_score"] = int(m2.danger_rating)
        if reroute_1:
            result["emergency_reroute"] = reroute_1
        if reroute_2:
            mission2["emergency_reroute"] = reroute_2
        if req.push_to_driver:
            _push_sim_job(
                result,
                ambulance_id=req.ambulance_id,
                ambulance_lat=req.ambulance_lat,
                ambulance_lng=req.ambulance_lng,
                pickup_lat=req.pickup_lat,
                pickup_lng=req.pickup_lng,
                pickup_name=req.pickup_address or "simulated pickup",
                dest_name=dest_address or "simulated destination",
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                hospital=assigned_hospital,
                emergency_category=req.emergency_category,
                flags=flags_1,
                traffic_points=traffic,
                slot=1,
            )
            _push_sim_job(
                mission2,
                ambulance_id=m2.ambulance_id,
                ambulance_lat=m2.ambulance_lat,
                ambulance_lng=m2.ambulance_lng,
                pickup_lat=m2.pickup_lat,
                pickup_lng=m2.pickup_lng,
                pickup_name=m2.pickup_address or "simulated pickup",
                dest_name=dest2_address or "simulated destination",
                dest_lat=dest2_lat,
                dest_lng=dest2_lng,
                hospital=hospital_2,
                emergency_category=m2.emergency_category,
                flags=flags_2,
                traffic_points=traffic,
                slot=2,
            )
        return {"status": "success", "data": result}

    result = await asyncio.to_thread(
        simulate_custom_route,
        sim_ambulance,
        (req.pickup_lat, req.pickup_lng),
        (dest_lat, dest_lng),
        is_raining=is_raining,
        prefer=req.prefer or "fastest",
        traffic_points=traffic,
        previous_drop_sig=req.previous_drop_sig,
        previous_pickup_sig=req.previous_pickup_sig,
        hospital=assigned_hospital,
        emergency_category=req.emergency_category,
        flags=flags_1,
        hospital_rerouted=bool(reroute_1 and reroute_1.get("changed")),
    )
    _annotate_sim_result(
        result,
        pickup_lat=req.pickup_lat,
        pickup_lng=req.pickup_lng,
        pickup_address=req.pickup_address,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        dest_address=dest_address,
        ambulance_lat=req.ambulance_lat,
        ambulance_lng=req.ambulance_lng,
        ambulance_address=req.ambulance_address,
    )
    if reroute_1:
        result["emergency_reroute"] = reroute_1
    result["patient"] = sim_patient_for_slot(1)
    if req.danger_rating is not None:
        result["condition_score"] = int(req.danger_rating)
    if req.push_to_driver:
        _push_sim_job(
            result,
            ambulance_id=req.ambulance_id,
            ambulance_lat=req.ambulance_lat,
            ambulance_lng=req.ambulance_lng,
            pickup_lat=req.pickup_lat,
            pickup_lng=req.pickup_lng,
            pickup_name=req.pickup_address or "simulated pickup",
            dest_name=dest_address or "simulated destination",
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            hospital=assigned_hospital,
            emergency_category=req.emergency_category,
            flags=flags_1,
            traffic_points=traffic,
            slot=1,
        )
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
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(default=None)):
    raw = (token or "").strip() or (websocket.headers.get("authorization") or "")
    if raw.lower().startswith("bearer "):
        raw = raw.split(" ", 1)[1].strip()
    try:
        user = user_from_access_token(raw)
    except HTTPException:
        await websocket.close(code=4401)
        return
    profile = user.get("profile") or {}
    if profile.get("status") != "active" or profile.get("role") not in ("staff", "driver", "doctor", "main_admin"):
        await websocket.close(code=4403)
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast({"message": data, "type": "echo"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
