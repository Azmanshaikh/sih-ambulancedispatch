from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.fleet import BMSIT, get_ambulance

_missions: dict[str, dict[str, Any]] = {}
_vitals: dict[str, dict[str, Any]] = {}
_records: dict[str, dict[str, Any]] = {}
_alerts: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_medical_record(user_id: str, record: dict[str, Any]) -> dict[str, Any]:
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
    return current


def get_medical_record(user_id: str) -> dict[str, Any]:
    return _records.get(user_id, {"user_id": user_id, "history": []})


def tick_vitals(user_id: str) -> dict[str, Any]:
    prev = _vitals.get(user_id)
    hr = 72 if not prev else prev["heart_rate"]
    spo2 = 98 if not prev else prev["spo2"]
    hr = int(max(58, min(118, hr + random.randint(-4, 4))))
    spo2 = int(max(93, min(100, spo2 + random.randint(-1, 1))))
    row = {"user_id": user_id, "heart_rate": hr, "spo2": spo2, "source": "mock-sensor"}
    _vitals[user_id] = row
    return row


def get_vitals(user_id: str) -> dict[str, Any]:
    return _vitals.get(user_id) or tick_vitals(user_id)


def save_mission(mission: dict[str, Any]) -> dict[str, Any]:
    amb_id = mission.get("ambulance_id")
    patient_id = mission.get("patient_id")
    mission.setdefault("phase", "pickup")
    mission.setdefault("id", str(uuid.uuid4()))
    if amb_id:
        _missions[f"amb:{amb_id}"] = mission
    if patient_id:
        _missions[f"patient:{patient_id}"] = mission
    _missions["latest"] = mission
    return mission


def get_mission_for_ambulance(ambulance_id: str | None) -> dict[str, Any] | None:
    if ambulance_id:
        found = _missions.get(f"amb:{ambulance_id}")
        if found:
            return found
    return None


def get_mission_for_patient(patient_id: str) -> dict[str, Any] | None:
    return _missions.get(f"patient:{patient_id}") or None


def get_latest_mission() -> dict[str, Any] | None:
    return _missions.get("latest")


def set_mission_phase(phase: str, ambulance_id: str | None = None) -> dict[str, Any] | None:
    if phase not in ("pickup", "drop"):
        raise ValueError("phase must be pickup or drop")
    mission = get_mission_for_ambulance(ambulance_id) if ambulance_id else get_latest_mission()
    if not mission:
        mission = get_latest_mission()
    if not mission:
        return None
    mission["phase"] = phase
    save_mission(mission)
    return mission


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
    return alert


def list_alerts(role: str, ambulance_id: str | None = None, unread_only: bool = False) -> list[dict[str, Any]]:
    rows = [a for a in _alerts if a.get("role") == role]
    if role == "driver" and ambulance_id:
        rows = [a for a in rows if a.get("ambulance_id") == ambulance_id]
    if unread_only:
        rows = [a for a in rows if not a.get("read")]
    return rows


def ack_alert(alert_id: str) -> dict[str, Any] | None:
    for alert in _alerts:
        if str(alert.get("id")) == str(alert_id):
            alert["read"] = True
            return alert
    return None


def unread_count(role: str, ambulance_id: str | None = None) -> int:
    return len(list_alerts(role, ambulance_id, unread_only=True))
