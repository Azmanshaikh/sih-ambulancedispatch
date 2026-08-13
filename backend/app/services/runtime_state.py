from __future__ import annotations

import random
from typing import Any

from app.services.fleet import BMSIT, get_ambulance

_missions: dict[str, dict[str, Any]] = {}
_vitals: dict[str, dict[str, Any]] = {}
_records: dict[str, dict[str, Any]] = {}


def set_medical_record(user_id: str, record: dict[str, Any]) -> dict[str, Any]:
    current = _records.get(user_id, {})
    current.update(record)
    current["user_id"] = user_id
    _records[user_id] = current
    return current


def get_medical_record(user_id: str) -> dict[str, Any]:
    return _records.get(user_id, {"user_id": user_id})


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
    return out
