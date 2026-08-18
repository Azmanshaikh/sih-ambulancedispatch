from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.fleet import BMSIT, get_ambulance, follow_drop_leg, release_ambulance
from app.core.supabase import rest_insert, rest_select, rest_update, rest_upsert

_missions: dict[str, dict[str, Any]] = {}
_vitals: dict[str, dict[str, Any]] = {}
_records: dict[str, dict[str, Any]] = {}
_alerts: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_medical_record(user_id: str, record: dict[str, Any], patient_email: str | None = None) -> dict[str, Any]:
    current = _records.get(user_id, {"user_id": user_id, "history": []})
    history = list(current.get("history") or [])
    snapshot = {
        "cardiac": bool(record.get("cardiac")),
        "diabetes": bool(record.get("diabetes")),
        "epilepsy": bool(record.get("epilepsy")),
        "pregnant": bool(record.get("pregnant")),
        "notes": record.get("notes") or "",
        "at": _now(),
    }
    history.append(snapshot)
    current.update(record)
    current["user_id"] = user_id
    current["history"] = history[-20:]
    _records[user_id] = current
    rest_insert(
        "medical_events",
        {
            "user_id": user_id if _looks_uuid(user_id) else None,
            "patient_email": patient_email,
            "cardiac": snapshot["cardiac"],
            "diabetes": snapshot["diabetes"],
            "epilepsy": snapshot["epilepsy"],
            "pregnant": snapshot["pregnant"],
            "notes": snapshot["notes"],
        },
    )
    return current


def get_medical_record(user_id: str) -> dict[str, Any]:
    mem = _records.get(user_id)
    events = rest_select(
        "medical_events",
        {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc"},
    )
    history = [
        {
            "cardiac": e.get("cardiac"),
            "diabetes": e.get("diabetes"),
            "epilepsy": e.get("epilepsy"),
            "pregnant": e.get("pregnant"),
            "notes": e.get("notes") or "",
            "at": e.get("created_at"),
        }
        for e in events
    ]
    if mem:
        if history:
            mem = dict(mem)
            mem["history"] = history
        return mem
    if history:
        latest = history[0]
        return {"user_id": user_id, **latest, "history": history}
    return {"user_id": user_id, "history": []}


def _looks_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _persist_case(mission: dict[str, Any]) -> None:
    medical = get_medical_record(mission.get("patient_id") or "") if mission.get("patient_id") else {}
    rest_upsert(
        "dispatch_cases",
        {
            "id": mission.get("id"),
            "patient_id": mission.get("patient_id") if _looks_uuid(mission.get("patient_id")) else None,
            "patient_name": mission.get("patient_name"),
            "patient_email": mission.get("patient_email"),
            "ambulance_id": mission.get("ambulance_id"),
            "hospital_name": mission.get("hospital_name"),
            "hospital": mission.get("hospital"),
            "pickup": mission.get("pickup"),
            "route": mission.get("route") or [],
            "pickup_route": mission.get("pickup_route") or [],
            "eta_minutes": mission.get("eta_minutes"),
            "pickup_minutes": mission.get("pickup_minutes"),
            "transport_minutes": mission.get("transport_minutes"),
            "phase": mission.get("phase") or "pickup",
            "medical": {
                "cardiac": medical.get("cardiac"),
                "diabetes": medical.get("diabetes"),
                "epilepsy": medical.get("epilepsy"),
                "pregnant": medical.get("pregnant"),
                "notes": medical.get("notes") or mission.get("notes"),
                "analysis": mission.get("analysis") or "",
                "history": medical.get("history") or [],
            },
        },
    )


def tick_vitals(user_id: str) -> dict[str, Any]:
    prev = _vitals.get(user_id)
    hr = 72 if not prev else prev["heart_rate"]
    spo2 = 98 if not prev else prev["spo2"]
    sys = 118 if not prev else prev.get("bp_sys", 118)
    dia = 76 if not prev else prev.get("bp_dia", 76)
    temp = 36.8 if not prev else prev.get("temperature_c", 36.8)
    resp = 16 if not prev else prev.get("resp_rate", 16)
    hr = int(max(58, min(118, hr + random.randint(-4, 4))))
    spo2 = int(max(93, min(100, spo2 + random.randint(-1, 1))))
    sys = int(max(100, min(145, sys + random.randint(-3, 3))))
    dia = int(max(60, min(95, dia + random.randint(-2, 2))))
    temp = round(max(36.2, min(38.4, temp + random.uniform(-0.1, 0.1))), 1)
    resp = int(max(12, min(22, resp + random.randint(-1, 1))))
    row = {
        "user_id": user_id,
        "heart_rate": hr,
        "spo2": spo2,
        "bp_sys": sys,
        "bp_dia": dia,
        "temperature_c": temp,
        "resp_rate": resp,
        "source": "mock-sensor",
    }
    _vitals[user_id] = row
    return row


def get_vitals(user_id: str) -> dict[str, Any]:
    return _vitals.get(user_id) or tick_vitals(user_id)


def save_mission(mission: dict[str, Any]) -> dict[str, Any]:
    amb_id = mission.get("ambulance_id")
    patient_id = mission.get("patient_id")
    mission.setdefault("phase", "pickup")
    mission.setdefault("id", str(uuid.uuid4()))
    mission.setdefault("phase_started_at", _now())
    mission.setdefault("created_at", mission.get("phase_started_at") or _now())
    _missions[f"id:{mission['id']}"] = mission
    if amb_id:
        _missions[f"amb:{amb_id}"] = mission
    if patient_id:
        _missions[f"patient:{patient_id}"] = mission
    _missions["latest"] = mission
    _persist_case(mission)
    return mission


def get_mission_for_ambulance(ambulance_id: str | None) -> dict[str, Any] | None:
    if ambulance_id:
        found = _missions.get(f"amb:{ambulance_id}")
        if found:
            return found
    return None


def get_mission_for_patient(patient_id: str) -> dict[str, Any] | None:
    return _missions.get(f"patient:{patient_id}") or None


def list_active_missions() -> list[dict[str, Any]]:
    seen: set[str] = set()
    active: list[dict[str, Any]] = []
    for key, mission in _missions.items():
        if not isinstance(mission, dict):
            continue
        if key == "latest" or key.startswith("patient:"):
            continue
        if not is_live_mission(mission):
            continue
        mid = str(mission.get("id") or key)
        if mid in seen:
            continue
        seen.add(mid)
        active.append(mission)
    active.sort(key=lambda m: int(m.get("priority") or 1), reverse=True)
    return active


def is_live_mission(mission: dict[str, Any] | None) -> bool:
    if not mission:
        return False
    if (mission.get("phase") or "pickup") not in ("pickup", "drop"):
        return False
    raw = mission.get("phase_started_at") or mission.get("created_at")
    if not raw:
        return True
    try:
        started = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - started).total_seconds() > 40 * 60:
            return False
    except Exception:
        return True
    return True


def live_mission_or_none(mission: dict[str, Any] | None) -> dict[str, Any] | None:
    return mission if is_live_mission(mission) else None


def get_latest_mission() -> dict[str, Any] | None:
    latest = live_mission_or_none(_missions.get("latest"))
    if latest:
        return latest
    actives = list_active_missions()
    if actives:
        _missions["latest"] = actives[0]
        return actives[0]
    rows = rest_select(
        "dispatch_cases",
        {
            "select": "*",
            "order": "created_at.desc",
            "limit": "8",
            "phase": "in.(pickup,drop)",
        },
    )
    if not rows:
        return None
    for row in rows:
        mission = {
            "id": row.get("id"),
            "patient_id": row.get("patient_id"),
            "patient_name": row.get("patient_name"),
            "patient_email": row.get("patient_email"),
            "ambulance_id": row.get("ambulance_id"),
            "hospital_name": row.get("hospital_name"),
            "hospital": row.get("hospital"),
            "pickup": row.get("pickup"),
            "route": row.get("route") or [],
            "pickup_route": row.get("pickup_route") or [],
            "eta_minutes": row.get("eta_minutes"),
            "pickup_minutes": row.get("pickup_minutes"),
            "transport_minutes": row.get("transport_minutes"),
            "phase": row.get("phase") or "pickup",
            "created_at": row.get("created_at"),
            "report": row.get("report") or (row.get("medical") or {}).get("report"),
        }
        if not is_live_mission(mission):
            continue
        _missions["latest"] = mission
        if mission.get("ambulance_id"):
            _missions[f"amb:{mission['ambulance_id']}"] = mission
        if mission.get("patient_id"):
            _missions[f"patient:{mission['patient_id']}"] = mission
        return mission
    return None


def set_mission_phase(phase: str, ambulance_id: str | None = None) -> dict[str, Any] | None:
    if phase not in ("pickup", "drop", "complete"):
        raise ValueError("phase must be pickup, drop, or complete")
    mission = get_mission_for_ambulance(ambulance_id) if ambulance_id else get_latest_mission()
    if not mission:
        mission = get_latest_mission()
    if not mission:
        return None
    if mission.get("phase") == "complete" and phase != "complete":
        return mission
    prev = mission.get("phase")
    mission["phase"] = phase
    if prev != phase:
        mission["phase_started_at"] = _now()
    amb_id = mission.get("ambulance_id")
    if phase == "drop":
        follow_drop_leg(amb_id)
    if phase == "complete":
        mission["completed_at"] = _now()
        release_ambulance(amb_id)
    save_mission(mission)
    return mission


def _phase_age_seconds(mission: dict[str, Any]) -> float:
    raw = mission.get("phase_started_at") or mission.get("created_at")
    if not raw:
        return 0.0
    try:
        started = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - started).total_seconds()
    except Exception:
        return 0.0


def apply_fleet_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Auto-advance pickup → drop → complete for every active mission."""
    changed: list[dict[str, Any]] = []
    by_unit: dict[str, list[dict[str, Any]]] = {}
    for event in events or []:
        amb_id = event.get("ambulance_id")
        if amb_id:
            by_unit.setdefault(str(amb_id), []).append(event)

    for mission in list(list_active_missions()):
        amb_id = mission.get("ambulance_id")
        updated = None
        for event in by_unit.get(str(amb_id or ""), []):
            arrived = event.get("arrived")
            phase = mission.get("phase") or "pickup"
            if arrived == "pickup" and phase == "pickup":
                updated = set_mission_phase("drop", amb_id)
                mission = updated or mission
            elif arrived == "drop" and phase in ("pickup", "drop"):
                updated = set_mission_phase("complete", amb_id)
                mission = updated or mission
        if mission and mission.get("phase") != "complete":
            age = _phase_age_seconds(mission)
            phase = mission.get("phase") or "pickup"
            if phase == "pickup" and age >= 22:
                updated = set_mission_phase("drop", amb_id)
            elif phase == "drop" and age >= 22:
                updated = set_mission_phase("complete", amb_id)
        if updated:
            changed.append(updated)
    return changed


def enrich_mission(mission: dict[str, Any] | None) -> dict[str, Any] | None:
    if not mission:
        return None
    amb = get_ambulance(mission.get("ambulance_id") or "")
    out = dict(mission)
    out["driver_location"] = amb
    out["pickup"] = mission.get("pickup") or {
        "name": BMSIT["name"],
        "lat": BMSIT["lat"],
        "lng": BMSIT["lng"],
    }
    out["pickup_route"] = mission.get("pickup_route") or []
    out["drop_route"] = mission.get("route") or []
    out["phase"] = mission.get("phase") or "pickup"
    return out


def push_alert(
    role: str,
    title: str,
    body: str,
    ambulance_id: str | None = None,
    mission_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alert = {
        "id": str(uuid.uuid4()),
        "role": role,
        "ambulance_id": ambulance_id,
        "title": title,
        "body": body,
        "mission_id": mission_id,
        "created_at": _now(),
        "read": False,
        **(extra or {}),
    }
    _alerts.insert(0, alert)
    _alerts[:] = _alerts[:80]
    rest_insert(
        "dispatch_alerts",
        {
            "id": alert["id"],
            "role": role,
            "ambulance_id": ambulance_id,
            "title": title,
            "body": body,
            "mission_id": mission_id if _looks_uuid(mission_id) else None,
            "payload": extra or {},
            "read": False,
            "created_at": alert["created_at"],
        },
    )
    return alert


def list_alerts(role: str, ambulance_id: str | None = None, unread_only: bool = False) -> list[dict[str, Any]]:
    params: dict[str, str] = {"role": f"eq.{role}", "select": "*", "order": "created_at.desc"}
    if role == "driver" and ambulance_id:
        params["ambulance_id"] = f"eq.{ambulance_id}"
    db_rows = rest_select("dispatch_alerts", params)
    merged: dict[str, dict[str, Any]] = {}
    for row in db_rows:
        payload = row.get("payload") or {}
        merged[str(row.get("id"))] = {**payload, **row}
    for alert in _alerts:
        if alert.get("role") != role:
            continue
        if role == "driver" and ambulance_id and alert.get("ambulance_id") != ambulance_id:
            continue
        merged[str(alert.get("id"))] = alert
    rows = sorted(merged.values(), key=lambda a: a.get("created_at") or "", reverse=True)
    if unread_only:
        rows = [a for a in rows if not a.get("read")]
    return rows


def ack_alert(alert_id: str) -> dict[str, Any] | None:
    found = None
    for alert in _alerts:
        if str(alert.get("id")) == str(alert_id):
            alert["read"] = True
            found = alert
            break
    rest_update("dispatch_alerts", {"id": f"eq.{alert_id}"}, {"read": True})
    if found:
        return found
    rows = rest_select("dispatch_alerts", {"id": f"eq.{alert_id}", "select": "*"})
    return rows[0] if rows else None


def unread_count(role: str, ambulance_id: str | None = None) -> int:
    return len(list_alerts(role, ambulance_id, unread_only=True))


def list_dispatch_cases(limit: int = 40) -> list[dict[str, Any]]:
    rows = rest_select("dispatch_cases", {"select": "*", "order": "created_at.desc", "limit": str(limit)})
    extras = []
    seen = {str(r.get("id")) for r in rows}
    for mission in list_active_missions() + ([get_latest_mission()] if get_latest_mission() else []):
        if not mission:
            continue
        mid = str(mission.get("id"))
        if mid in seen:
            continue
        seen.add(mid)
        extras.append(
            {
                "id": mission.get("id"),
                "patient_id": mission.get("patient_id"),
                "patient_name": mission.get("patient_name"),
                "patient_email": mission.get("patient_email"),
                "ambulance_id": mission.get("ambulance_id"),
                "hospital_name": mission.get("hospital_name"),
                "hospital": mission.get("hospital"),
                "pickup": mission.get("pickup"),
                "phase": mission.get("phase"),
                "medical": get_medical_record(mission.get("patient_id") or "") if mission.get("patient_id") else {},
                "created_at": mission.get("created_at") or _now(),
                "priority": mission.get("priority"),
                "conflict": mission.get("conflict"),
            }
        )
    return extras + rows
