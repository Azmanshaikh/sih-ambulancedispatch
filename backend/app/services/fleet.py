"""Yelahanka / North Bangalore mock fleet + hospitals (tracked in-memory)."""

from __future__ import annotations

import copy
import math
import random
from typing import Any

# BMS Institute of Technology & Management, Avalahalli, Yelahanka
BMSIT = {
    "name": "BMSIT College, Avalahalli, Yelahanka",
    "lat": 13.1344,
    "lng": 77.5693,
}

_HOSPITAL_SEED: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "Cytecare Cancer Hospital",
        "lat": 13.1168,
        "lng": 77.5819,
        "available_beds": 14,
        "total_beds": 40,
        "specializations": ["Oncology", "Trauma", "ICU"],
        "phone": "080-2218-8888",
    },
    {
        "id": 2,
        "name": "Sparsh Hospital, Yelahanka",
        "lat": 13.0995,
        "lng": 77.5963,
        "available_beds": 8,
        "total_beds": 32,
        "specializations": ["Ortho", "Trauma", "Emergency"],
        "phone": "080-4911-1111",
    },
    {
        "id": 3,
        "name": "People Tree Hospitals, Yelahanka",
        "lat": 13.1018,
        "lng": 77.5805,
        "available_beds": 11,
        "total_beds": 28,
        "specializations": ["General", "Pediatric", "Emergency"],
        "phone": "080-2308-8888",
    },
    {
        "id": 4,
        "name": "Yelahanka Government Hospital",
        "lat": 13.1009,
        "lng": 77.5965,
        "available_beds": 22,
        "total_beds": 80,
        "specializations": ["General", "Emergency"],
        "phone": "080-2856-1234",
    },
    {
        "id": 5,
        "name": "Aster CMI Hospital, Hebbal",
        "lat": 13.0476,
        "lng": 77.5915,
        "available_beds": 6,
        "total_beds": 90,
        "specializations": ["Cardiac", "Trauma", "Neuro", "ICU"],
        "phone": "080-4342-0100",
    },
    {
        "id": 6,
        "name": "Manipal Hospital, Hebbal",
        "lat": 13.0494,
        "lng": 77.5929,
        "available_beds": 9,
        "total_beds": 70,
        "specializations": ["Cardiac", "Trauma", "Emergency"],
        "phone": "080-2502-4444",
    },
    {
        "id": 7,
        "name": "M.S. Ramaiah Memorial Hospital",
        "lat": 13.0306,
        "lng": 77.5648,
        "available_beds": 15,
        "total_beds": 120,
        "specializations": ["Trauma", "Cardiac", "Neuro"],
        "phone": "080-2360-8888",
    },
    {
        "id": 8,
        "name": "Bangalore Baptist Hospital",
        "lat": 13.0356,
        "lng": 77.5891,
        "available_beds": 7,
        "total_beds": 50,
        "specializations": ["General", "Emergency", "Pediatric"],
        "phone": "080-2202-4700",
    },
]

AMBULANCE_TYPES: dict[str, dict[str, Any]] = {
    "BLS": {"label": "Basic Life Support", "crew": "EMT crew", "equipment": "Oxygen, AED, first-aid and stretcher"},
    "ALS": {"label": "Advanced Life Support", "crew": "Paramedic / critical-care crew", "equipment": "Cardiac monitor, defibrillator, ventilator and emergency drugs"},
    "NEONATAL_PEDIATRIC": {"label": "Neonatal & Pediatric", "crew": "Pediatric transport crew", "equipment": "Pediatric equipment and neonatal transport support"},
    "BARIATRIC_ACCESSIBLE": {"label": "Bariatric & Accessible", "crew": "Specialist transport crew", "equipment": "Powered stretcher, ramp and mobility accommodation"},
}


def _unit(id: str, label: str, lat: float, lng: float, status: str, ambulance_type: str) -> dict[str, Any]:
    profile = AMBULANCE_TYPES[ambulance_type]
    return {
        "id": id,
        "label": label,
        "lat": lat,
        "lng": lng,
        "status": status,
        "ambulance_type": ambulance_type,
        "type_label": profile["label"],
        "crew": profile["crew"],
        "equipment": profile["equipment"],
    }


_AMBULANCE_SEED: list[dict[str, Any]] = [
    _unit("AMB-101", "Kempegowda Airport", 13.1989, 77.7063, "available", "BLS"),
    _unit("AMB-102", "Devanahalli", 13.2475, 77.7138, "available", "BLS"),
    _unit("AMB-103", "Doddaballapur", 13.2916, 77.5413, "available", "BLS"),
    _unit("AMB-104", "Rajankunte", 13.1784, 77.5612, "available", "BLS"),
    _unit("AMB-105", "Hunasamaranahalli", 13.1678, 77.6215, "available", "BLS"),
    _unit("AMB-106", "Trumpet Interchange", 13.1712, 77.6554, "available", "ALS"),
    _unit("AMB-107", "Hessarghatta", 13.1396, 77.4872, "available", "BLS"),
    _unit("AMB-108", "Peenya Industrial", 13.0284, 77.5141, "available", "ALS"),
    _unit("AMB-109", "Jalahalli Cross", 13.0398, 77.5468, "available", "ALS"),
    _unit("AMB-110", "RT Nagar", 13.0246, 77.5942, "available", "ALS"),
    _unit("AMB-111", "Hennur Junction", 13.0302, 77.6384, "enroute", "NEONATAL_PEDIATRIC"),
    _unit("AMB-112", "Kothanur", 13.0624, 77.6418, "available", "BLS"),
    _unit("AMB-113", "Bettahalasuru", 13.1628, 77.6310, "available", "BLS"),
    _unit("AMB-114", "Singanayakanahalli", 13.1762, 77.5448, "available", "NEONATAL_PEDIATRIC"),
    _unit("AMB-115", "Thanisandra Main", 13.0482, 77.6320, "busy", "BARIATRIC_ACCESSIBLE"),
    _unit("AMB-116", "Hebbal Kempapura", 13.0448, 77.6126, "available", "ALS"),
    _unit("AMB-117", "Chikkabanavara", 13.0842, 77.5016, "available", "BARIATRIC_ACCESSIBLE"),
    _unit("AMB-118", "BIAL Cargo Road", 13.1894, 77.6898, "available", "BLS"),
]

_fleet: list[dict[str, Any]] = []
_hospitals: list[dict[str, Any]] = []


def init_fleet() -> None:
    global _fleet, _hospitals
    _hospitals = copy.deepcopy(_HOSPITAL_SEED)
    _fleet = []
    for seed in _AMBULANCE_SEED:
        unit = copy.deepcopy(seed)
        unit["home_lat"] = seed["lat"]
        unit["home_lng"] = seed["lng"]
        unit["heading"] = random.uniform(0, 2 * math.pi)
        _fleet.append(unit)


def get_hospitals() -> list[dict[str, Any]]:
    if not _hospitals:
        init_fleet()
    return copy.deepcopy(_hospitals)


def hospital_directory() -> list[dict[str, Any]]:
    return [{"id": h["id"], "name": h["name"]} for h in get_hospitals()]


def get_hospital(hospital_id: int | str | None) -> dict[str, Any] | None:
    if hospital_id is None or hospital_id == "":
        return None
    try:
        hid = int(hospital_id)
    except (TypeError, ValueError):
        return None
    for h in get_hospitals():
        if int(h["id"]) == hid:
            return h
    return None


def update_hospital_beds(
    hospital_id: int,
    available_beds: int,
    total_beds: int | None = None,
) -> dict[str, Any]:
    if not _hospitals:
        init_fleet()
    for h in _hospitals:
        if int(h["id"]) != int(hospital_id):
            continue
        available = int(available_beds)
        total = int(total_beds) if total_beds is not None else int(h["total_beds"])
        if available < 0:
            raise ValueError("Available beds cannot be negative")
        if total < 1:
            raise ValueError("Total beds must be at least 1")
        if available > total:
            raise ValueError("Available beds cannot exceed total beds")
        h["available_beds"] = available
        h["total_beds"] = total
        return copy.deepcopy(h)
    raise ValueError("Hospital not found")


def get_ambulances() -> list[dict[str, Any]]:
    if not _fleet:
        init_fleet()
    public = []
    for unit in _fleet:
        public.append(
            {
                "id": unit["id"],
                "label": unit["label"],
                "lat": round(unit["lat"], 6),
                "lng": round(unit["lng"], 6),
                "status": unit["status"],
                "ambulance_type": unit["ambulance_type"],
                "type_label": unit["type_label"],
                "crew": unit["crew"],
                "equipment": unit["equipment"],
                "location": (unit["lat"], unit["lng"]),
            }
        )
    return public


def get_ambulance(ambulance_id: str) -> dict[str, Any] | None:
    if not _fleet:
        init_fleet()
    for unit in _fleet:
        if unit["id"] == ambulance_id:
            return {
                "id": unit["id"],
                "label": unit["label"],
                "lat": round(unit["lat"], 6),
                "lng": round(unit["lng"], 6),
                "status": unit["status"],
                "ambulance_type": unit["ambulance_type"],
                "type_label": unit["type_label"],
                "crew": unit["crew"],
                "equipment": unit["equipment"],
            }
    return None


def place_ambulance(ambulance_id: str, lat: float, lng: float) -> None:
    if not _fleet:
        init_fleet()
    for unit in _fleet:
        if unit["id"] != ambulance_id:
            continue
        unit["lat"] = float(lat)
        unit["lng"] = float(lng)
        break


def assign_ambulance(
    ambulance_id: str,
    pickup_path: list[tuple[float, float]] | None = None,
    drop_path: list[tuple[float, float]] | None = None,
) -> None:
    for unit in _fleet:
        if unit["id"] != ambulance_id:
            continue
        unit["status"] = "dispatched"
        unit["pickup_path"] = list(pickup_path or [])
        unit["drop_path"] = list(drop_path or [])
        unit["path"] = list(pickup_path or [])
        unit["path_i"] = 0
        unit["leg"] = "pickup"
        if unit["path"]:
            unit["lat"] = float(unit["path"][0][0])
            unit["lng"] = float(unit["path"][0][1])
        break


def release_ambulance(ambulance_id: str | None) -> None:
    if not ambulance_id:
        return
    for unit in _fleet:
        if unit["id"] != ambulance_id:
            continue
        unit["status"] = "available"
        unit["path"] = []
        unit["pickup_path"] = []
        unit["drop_path"] = []
        unit["path_i"] = 0
        unit["leg"] = None
        break


def update_ambulance_paths(
    ambulance_id: str | None,
    pickup_path: list[tuple[float, float]] | None = None,
    drop_path: list[tuple[float, float]] | None = None,
) -> None:
    if not ambulance_id:
        return
    for unit in _fleet:
        if unit["id"] != ambulance_id:
            continue
        here = (float(unit["lat"]), float(unit["lng"]))
        if pickup_path is not None:
            unit["pickup_path"] = list(pickup_path)
        if drop_path is not None:
            unit["drop_path"] = list(drop_path)
        if unit.get("leg") == "drop" and drop_path is not None:
            path = list(drop_path)
            if path and (abs(path[0][0] - here[0]) > 1e-6 or abs(path[0][1] - here[1]) > 1e-6):
                path = [here] + path
            unit["path"] = path
            unit["path_i"] = 0
        elif unit.get("leg") == "pickup" and pickup_path is not None:
            path = list(pickup_path)
            if path and (abs(path[0][0] - here[0]) > 1e-6 or abs(path[0][1] - here[1]) > 1e-6):
                path = [here] + path
            unit["path"] = path
            unit["path_i"] = 0
        elif unit.get("leg") == "pickup" and drop_path is not None:
            unit["drop_path"] = list(drop_path)
        break


def follow_drop_leg(ambulance_id: str | None) -> None:
    if not ambulance_id:
        return
    for unit in _fleet:
        if unit["id"] != ambulance_id:
            continue
        unit["status"] = "dispatched"
        unit["leg"] = "drop"
        unit["path"] = list(unit.get("drop_path") or [])
        unit["path_i"] = 0
        if unit["path"]:
            unit["lat"] = float(unit["path"][0][0])
            unit["lng"] = float(unit["path"][0][1])
        break


def _advance_along_path(unit: dict[str, Any]) -> str | None:
    path = unit.get("path") or []
    if len(path) < 2:
        return None
    remaining = max(1, len(path) - 1 - int(unit.get("path_i") or 0))
    step = max(1, remaining // 10)
    unit["path_i"] = min(int(unit.get("path_i") or 0) + step, len(path) - 1)
    pt = path[unit["path_i"]]
    unit["lat"] = float(pt[0])
    unit["lng"] = float(pt[1])
    if unit["path_i"] >= len(path) - 1:
        return unit.get("leg") or "pickup"
    return None


def tick_fleet() -> list[dict[str, Any]]:
    """Idle units drift near base. Assigned units follow pickup then drop routes."""
    if not _fleet:
        init_fleet()
    events: list[dict[str, Any]] = []
    for unit in _fleet:
        arrived = _advance_along_path(unit) if unit.get("status") == "dispatched" and unit.get("path") else None
        if arrived:
            events.append({"ambulance_id": unit["id"], "arrived": arrived})
            continue
        if unit.get("path"):
            continue
        if unit["status"] == "busy":
            step = 0.00008
        elif unit["status"] == "dispatched":
            step = 0.00022
        else:
            step = 0.00012
        unit["heading"] += random.uniform(-0.6, 0.6)
        unit["lat"] += math.cos(unit["heading"]) * step
        unit["lng"] += math.sin(unit["heading"]) * step
        dlat = unit["lat"] - unit["home_lat"]
        dlng = unit["lng"] - unit["home_lng"]
        if (dlat * dlat + dlng * dlng) > (0.032**2):
            unit["heading"] = math.atan2(-dlng, -dlat)
            unit["lat"] = unit["home_lat"] + dlat * 0.85
            unit["lng"] = unit["home_lng"] + dlng * 0.85
    return events
