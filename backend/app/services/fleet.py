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

_AMBULANCE_SEED: list[dict[str, Any]] = [
    {"id": "AMB-101", "label": "Kempegowda Airport", "lat": 13.1989, "lng": 77.7063, "status": "available"},
    {"id": "AMB-102", "label": "Devanahalli", "lat": 13.2475, "lng": 77.7138, "status": "available"},
    {"id": "AMB-103", "label": "Doddaballapur", "lat": 13.2916, "lng": 77.5413, "status": "available"},
    {"id": "AMB-104", "label": "Rajankunte", "lat": 13.1784, "lng": 77.5612, "status": "available"},
    {"id": "AMB-105", "label": "Hunasamaranahalli", "lat": 13.1678, "lng": 77.6215, "status": "available"},
    {"id": "AMB-106", "label": "Trumpet Interchange", "lat": 13.1712, "lng": 77.6554, "status": "available"},
    {"id": "AMB-107", "label": "Hessarghatta", "lat": 13.1396, "lng": 77.4872, "status": "available"},
    {"id": "AMB-108", "label": "Peenya Industrial", "lat": 13.0284, "lng": 77.5141, "status": "available"},
    {"id": "AMB-109", "label": "Jalahalli Cross", "lat": 13.0398, "lng": 77.5468, "status": "available"},
    {"id": "AMB-110", "label": "RT Nagar", "lat": 13.0246, "lng": 77.5942, "status": "available"},
    {"id": "AMB-111", "label": "Hennur Junction", "lat": 13.0302, "lng": 77.6384, "status": "enroute"},
    {"id": "AMB-112", "label": "Kothanur", "lat": 13.0624, "lng": 77.6418, "status": "available"},
    {"id": "AMB-113", "label": "Bettahalasuru", "lat": 13.1628, "lng": 77.6310, "status": "available"},
    {"id": "AMB-114", "label": "Singanayakanahalli", "lat": 13.1762, "lng": 77.5448, "status": "available"},
    {"id": "AMB-115", "label": "Thanisandra Main", "lat": 13.0482, "lng": 77.6320, "status": "busy"},
    {"id": "AMB-116", "label": "Hebbal Kempapura", "lat": 13.0448, "lng": 77.6126, "status": "available"},
    {"id": "AMB-117", "label": "Chikkabanavara", "lat": 13.0842, "lng": 77.5016, "status": "available"},
    {"id": "AMB-118", "label": "BIAL Cargo Road", "lat": 13.1894, "lng": 77.6898, "status": "available"},
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
            }
    return None


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
