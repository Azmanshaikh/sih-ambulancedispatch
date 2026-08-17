"""Emergency corridor occupancy, police/rescue geofencing, and timed SMS alerts."""

from __future__ import annotations

import math
from typing import Any

from app.services.dispatch_optimizer import optimizer
from app.services.fleet import get_ambulance, update_ambulance_paths
from app.services.sms import list_sms, send_sms

CELL_M = 90.0
BUFFER_M = 200.0
ALERT_WINDOW_S = 180.0
DELAY_THRESHOLD_S = 90.0
SHARE_SPEED_KMH = 20.0
PRIORITY_LABELS = {5: "cardiac", 4: "pregnant", 3: "epilepsy", 2: "diabetes", 1: "standard"}

_POSTS: list[dict[str, Any]] = [
    {"id": "TP-01", "name": "Yelahanka Traffic Police Station", "lat": 13.1006, "lng": 77.5960, "phone": "+919845010001", "kind": "traffic_police"},
    {"id": "TP-02", "name": "Yelahanka New Town PS", "lat": 13.0890, "lng": 77.5830, "phone": "+919845010002", "kind": "traffic_police"},
    {"id": "TP-03", "name": "Allalasandra Junction", "lat": 13.0855, "lng": 77.5950, "phone": "+919845010003", "kind": "traffic_police"},
    {"id": "TP-04", "name": "Bellary Road / NH44 Yelahanka", "lat": 13.1100, "lng": 77.5900, "phone": "+919845010004", "kind": "traffic_police"},
    {"id": "TP-05", "name": "Kogilu Cross", "lat": 13.1150, "lng": 77.6100, "phone": "+919845010005", "kind": "traffic_police"},
    {"id": "TP-06", "name": "Trumpet Interchange Traffic", "lat": 13.1712, "lng": 77.6554, "phone": "+919845010006", "kind": "traffic_police"},
    {"id": "TP-07", "name": "Hebbal Flyover Traffic Post", "lat": 13.0505, "lng": 77.5915, "phone": "+919845010007", "kind": "traffic_police"},
    {"id": "TP-08", "name": "Hebbal Kempapura Junction", "lat": 13.0448, "lng": 77.6126, "phone": "+919845010008", "kind": "traffic_police"},
    {"id": "TP-09", "name": "BMSIT / Avalahalli Gate", "lat": 13.1344, "lng": 77.5693, "phone": "+919845010009", "kind": "traffic_police"},
    {"id": "TP-10", "name": "Puttenahalli Junction", "lat": 13.1200, "lng": 77.5750, "phone": "+919845010010", "kind": "traffic_police"},
    {"id": "TP-11", "name": "Yelahanka Satellite Town", "lat": 13.1070, "lng": 77.5750, "phone": "+919845010011", "kind": "traffic_police"},
    {"id": "TP-12", "name": "Jakkur Cross", "lat": 13.0780, "lng": 77.5970, "phone": "+919845010012", "kind": "traffic_police"},
    {"id": "TP-13", "name": "Doddaballapur Road Checkpost", "lat": 13.1500, "lng": 77.5550, "phone": "+919845010013", "kind": "traffic_police"},
    {"id": "RS-01", "name": "Fire Station Yelahanka", "lat": 13.1025, "lng": 77.5880, "phone": "+919845020001", "kind": "rescue"},
    {"id": "RS-02", "name": "Civil Defence North / Hebbal", "lat": 13.0700, "lng": 77.5900, "phone": "+919845020002", "kind": "rescue"},
    {"id": "RS-03", "name": "Kothanur Rescue Post", "lat": 13.0450, "lng": 77.6400, "phone": "+919845020003", "kind": "rescue"},
]

_alerted: set[str] = set()
_alerted_posts: dict[str, str] = {}


def get_posts() -> list[dict[str, Any]]:
    now_alerted = set(_alerted_posts)
    rows = []
    for post in _POSTS:
        row = dict(post)
        row["alerted"] = post["id"] in now_alerted
        row["last_unit"] = _alerted_posts.get(post["id"])
        rows.append(row)
    return rows


def mission_priority(flags: dict[str, Any] | None, override: int | None = None) -> int:
    if override is not None:
        try:
            return max(1, min(5, int(override)))
        except (TypeError, ValueError):
            pass
    flags = flags or {}
    if flags.get("cardiac"):
        return 5
    if flags.get("pregnant"):
        return 4
    if flags.get("epilepsy"):
        return 3
    if flags.get("diabetes"):
        return 2
    return 1


def priority_label(value: int) -> str:
    return PRIORITY_LABELS.get(int(value or 1), "standard")


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, h)))


def _as_latlng(pt: Any) -> tuple[float, float] | None:
    if not pt:
        return None
    if isinstance(pt, dict):
        lat, lng = pt.get("lat"), pt.get("lng")
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)
    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
        return float(pt[0]), float(pt[1])
    return None


def _normalize_path(path: list[Any] | None) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for pt in path or []:
        pair = _as_latlng(pt)
        if pair:
            out.append(pair)
    return out


def _cell_key(lat: float, lng: float, cell_m: float = CELL_M) -> tuple[int, int]:
    step = cell_m / 111_000.0
    return int(round(lat / step)), int(round(lng / step))


def path_cells(path: list[Any] | None) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    coords = _normalize_path(path)
    if not coords:
        return cells
    prev = coords[0]
    cells.add(_cell_key(*prev))
    for pt in coords[1:]:
        dist = _haversine_m(prev, pt)
        steps = max(1, int(dist / CELL_M))
        for i in range(1, steps + 1):
            t = i / steps
            lat = prev[0] + (pt[0] - prev[0]) * t
            lng = prev[1] + (pt[1] - prev[1]) * t
            cells.add(_cell_key(lat, lng))
        prev = pt
    return cells


def overlap_stats(path_a: list[Any], path_b: list[Any]) -> dict[str, Any]:
    cells_a = path_cells(path_a)
    cells_b = path_cells(path_b)
    inter = cells_a & cells_b
    km = len(inter) * (CELL_M / 1000.0)
    overlap_pts = [pt for pt in _normalize_path(path_a) if _cell_key(*pt) in inter]
    delay_s = (km / SHARE_SPEED_KMH) * 3600.0 if km else 0.0
    bbox = None
    if overlap_pts:
        lats = [p[0] for p in overlap_pts]
        lngs = [p[1] for p in overlap_pts]
        pad = 0.004
        bbox = (min(lats) - pad, min(lngs) - pad, max(lats) + pad, max(lngs) + pad)
    return {
        "cells": len(inter),
        "km": round(km, 2),
        "delay_seconds": round(delay_s, 1),
        "points": overlap_pts,
        "bbox": bbox,
    }


def _trim_from_location(path: list[tuple[float, float]], loc: dict[str, Any] | None) -> list[tuple[float, float]]:
    coords = _normalize_path(path)
    if not coords:
        return []
    if not loc or loc.get("lat") is None:
        return coords
    here = (float(loc["lat"]), float(loc["lng"]))
    idx = min(range(len(coords)), key=lambda i: _haversine_m(here, coords[i]))
    rest = coords[idx:]
    if rest and _haversine_m(here, rest[0]) > 40:
        rest = [here] + rest
    return rest


def remaining_path(mission: dict[str, Any]) -> list[tuple[float, float]]:
    loc = get_ambulance(mission.get("ambulance_id") or "")
    pickup = _normalize_path(mission.get("pickup_route") or [])
    drop = _normalize_path(mission.get("route") or mission.get("drop_route") or [])
    phase = mission.get("phase") or "pickup"
    if phase == "pickup":
        return _trim_from_location(pickup, loc) + drop
    return _trim_from_location(drop, loc)


def _point_to_path_m(point: tuple[float, float], path: list[tuple[float, float]]) -> float:
    if not path:
        return float("inf")
    return min(_haversine_m(point, pt) for pt in path[:: max(1, len(path) // 80)])


def posts_near_path(path: list[Any], buffer_m: float = BUFFER_M) -> list[dict[str, Any]]:
    coords = _normalize_path(path)
    found = []
    for post in _POSTS:
        dist = _point_to_path_m((post["lat"], post["lng"]), coords)
        if dist <= buffer_m:
            row = dict(post)
            row["distance_m"] = round(dist, 1)
            found.append(row)
    return found


def eta_to_post(path: list[tuple[float, float]], post: dict[str, Any], total_eta_s: float) -> float:
    coords = _normalize_path(path)
    if not coords:
        return float("inf")
    idx = min(range(len(coords)), key=lambda i: _haversine_m((post["lat"], post["lng"]), coords[i]))
    frac = idx / max(len(coords) - 1, 1)
    return max(0.0, float(total_eta_s) * frac)


def remaining_eta_seconds(mission: dict[str, Any]) -> float:
    phase = mission.get("phase") or "pickup"
    pickup = float(mission.get("pickup_minutes") or 0) * 60
    transport = float(mission.get("transport_minutes") or mission.get("eta_minutes") or 0) * 60
    total = pickup + transport if phase == "pickup" else max(transport, 30.0)
    orig = _normalize_path((mission.get("pickup_route") or []) + (mission.get("route") or []))
    if phase != "pickup":
        orig = _normalize_path(mission.get("route") or mission.get("drop_route") or [])
    rest = remaining_path(mission)
    orig_m = sum(_haversine_m(orig[i], orig[i + 1]) for i in range(len(orig) - 1)) or 1.0
    rest_m = sum(_haversine_m(rest[i], rest[i + 1]) for i in range(len(rest) - 1))
    return max(30.0, total * (rest_m / orig_m))


def _sms_key(mission_id: str, post_id: str) -> str:
    return f"{mission_id}:{post_id}"


def _direction(mission: dict[str, Any]) -> str:
    pickup = mission.get("pickup") or {}
    origin = pickup.get("name") if isinstance(pickup, dict) else "incident"
    dest = mission.get("hospital_name") or "hospital"
    return f"{origin} → {dest}"


def _alert_body(mission: dict[str, Any], post: dict[str, Any], eta_s: float) -> str:
    unit = mission.get("ambulance_id") or "ambulance"
    pri = priority_label(int(mission.get("priority") or 1))
    mins = max(1, int(round(eta_s / 60)))
    conflict = mission.get("conflict") or {}
    extra = ""
    if conflict.get("status") == "sequenced" and conflict.get("yield_to"):
        extra = f" Priority: {conflict.get('yield_to')} ({conflict.get('yield_to_label') or 'higher'}) has right of way."
    elif conflict.get("status") == "rerouted":
        extra = " Unit is on an alternate corridor to avoid delay."
    kind = "Rescue" if post.get("kind") == "rescue" else "Traffic police"
    return (
        f"JEEVAN ALERT: Ambulance {unit} ({pri}) arriving near {post['name']} in ~{mins} min. "
        f"{_direction(mission)}. Clear the corridor.{extra} — {kind}"
    )


def arm_corridor(mission: dict[str, Any]) -> list[dict[str, Any]]:
    return tick_mission_alerts(mission)


def tick_mission_alerts(mission: dict[str, Any]) -> list[dict[str, Any]]:
    from app.services.runtime_state import push_alert

    if not mission or mission.get("phase") == "complete":
        return []
    path = remaining_path(mission)
    if len(path) < 2:
        return []
    eta_s = remaining_eta_seconds(mission)
    sent: list[dict[str, Any]] = []
    for post in posts_near_path(path):
        eta = eta_to_post(path, post, eta_s)
        if eta > ALERT_WINDOW_S:
            continue
        key = _sms_key(str(mission.get("id")), post["id"])
        if key in _alerted:
            continue
        body = _alert_body(mission, post, eta)
        row = send_sms(
            post["phone"],
            body,
            post_id=post["id"],
            post_name=post["name"],
            mission_id=str(mission.get("id")),
            ambulance_id=mission.get("ambulance_id"),
        )
        _alerted.add(key)
        _alerted_posts[post["id"]] = mission.get("ambulance_id") or ""
        push_alert(
            "staff",
            "CORRIDOR SMS",
            f"{post['name']} alerted — {unit_line(mission)} in ~{max(1, int(round(eta / 60)))} min.",
            ambulance_id=mission.get("ambulance_id"),
            mission_id=mission.get("id"),
            extra={
                "post_id": post["id"],
                "post_name": post["name"],
                "sms_id": row.get("id"),
                "sms_status": row.get("status"),
            },
        )
        sent.append(row)
    return sent


def unit_line(mission: dict[str, Any]) -> str:
    return mission.get("ambulance_id") or "unit"


def tick_corridor_alerts() -> list[dict[str, Any]]:
    from app.services.runtime_state import list_active_missions

    sent: list[dict[str, Any]] = []
    live_posts: set[str] = set()
    for mission in list_active_missions():
        sent.extend(tick_mission_alerts(mission))
        for post in posts_near_path(remaining_path(mission)):
            if _sms_key(str(mission.get("id")), post["id"]) in _alerted:
                live_posts.add(post["id"])
    stale = [pid for pid in list(_alerted_posts) if pid not in live_posts]
    for pid in stale:
        _alerted_posts.pop(pid, None)
    return sent


def _pick_alternate(
    origin: tuple[float, float],
    dest: tuple[float, float],
    occupied_cells: set[tuple[int, int]],
    occupied_paths: list[list[tuple[float, float]]],
    bbox: tuple[float, float, float, float] | None,
    is_raining: bool,
    baseline_s: float,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    # NetworkX graph routes that penalize cells occupied by other ambulances.
    for prefer in ("fastest", "shortest"):
        g = optimizer.compute_route(
            origin,
            dest,
            emergency=True,
            is_raining=is_raining,
            avoid_areas=[bbox] if bbox else None,
            avoid_paths=occupied_paths,
            prefer=prefer,
            enrich=True,
        )
        if g.get("coords") and g["duration"] != float("inf"):
            candidates.append(g)
    for alt in optimizer.get_osrm_alternatives(origin, dest):
        dur = optimizer._apply_emergency_eta(float(alt["duration"]), is_raining)
        candidates.append({"duration": dur, "coords": alt["coords"], "source": "osrm-alt"})

    best = None
    best_overlap = 10**9
    for cand in candidates:
        cells = path_cells(cand["coords"])
        shared = len(cells & occupied_cells)
        extra = float(cand["duration"]) - baseline_s
        if shared < best_overlap or (shared == best_overlap and extra < float((best or {}).get("extra") or 10**9)):
            best = {**cand, "shared": shared, "extra": extra}
            best_overlap = shared
    return best


def resolve_conflict(
    result: dict[str, Any],
    *,
    priority: int,
    is_raining: bool = False,
    exclude_ambulance: str | None = None,
) -> dict[str, Any]:
    from app.services.runtime_state import list_active_missions, push_alert, save_mission

    pickup = _normalize_path(result.get("pickup_route") or [])
    drop = _normalize_path(result.get("route") or [])
    full = pickup + drop
    conflict: dict[str, Any] = {
        "status": "none",
        "overlap_km": 0,
        "delay_seconds": 0,
        "others": [],
        "overlap_route": [],
        "reason": None,
    }
    if len(full) < 2:
        result["conflict"] = conflict
        return result

    occupied: set[tuple[int, int]] = set()
    occupied_paths: list[list[tuple[float, float]]] = []
    overlaps: list[dict[str, Any]] = []
    for other in list_active_missions():
        if other.get("ambulance_id") == exclude_ambulance:
            continue
        if other.get("phase") == "complete":
            continue
        other_path = remaining_path(other)
        stats = overlap_stats(full, other_path)
        occupied |= path_cells(other_path)
        if other_path:
            occupied_paths.append(other_path)
        if stats["km"] <= 0:
            continue
        overlaps.append({"mission": other, **stats})

    if not overlaps:
        result["conflict"] = conflict
        return result

    worst = max(overlaps, key=lambda o: o["delay_seconds"])
    holders = [o for o in overlaps if int(o["mission"].get("priority") or 1) >= priority]
    lower = [o for o in overlaps if int(o["mission"].get("priority") or 1) < priority]
    delay = float(worst["delay_seconds"])
    overlap_pts = worst.get("points") or []
    conflict["overlap_km"] = worst["km"]
    conflict["delay_seconds"] = delay
    conflict["overlap_route"] = overlap_pts
    conflict["others"] = [o["mission"].get("ambulance_id") for o in overlaps]

    hospital = result.get("hospital") or {}
    dest = (float(hospital.get("lat") or 0), float(hospital.get("lng") or 0))
    incident = pickup[-1] if pickup else dest

    if holders and delay >= DELAY_THRESHOLD_S and dest[0]:
        holder = max(holders, key=lambda o: int(o["mission"].get("priority") or 1))
        holder_id = holder["mission"].get("ambulance_id")
        holder_pri = priority_label(int(holder["mission"].get("priority") or 1))
        alt = _pick_alternate(
            incident,
            dest,
            occupied,
            occupied_paths,
            holder.get("bbox"),
            is_raining,
            float(result.get("transport_minutes") or 0) * 60 or float(result.get("eta_seconds") or 0),
        )
        extra = float((alt or {}).get("extra") or 10**9)
        if alt and alt.get("coords") and extra < delay and extra < 12 * 60:
            result["route"] = alt["coords"]
            transport = round(float(alt["duration"]) / 60, 1)
            pickup_min = float(result.get("pickup_minutes") or 0)
            result["transport_minutes"] = transport
            result["eta_minutes"] = round(pickup_min + transport, 1)
            result["eta_seconds"] = int((pickup_min + transport) * 60)
            conflict["status"] = "rerouted"
            conflict["yield_to"] = holder_id
            conflict["yield_to_label"] = holder_pri
            conflict["reason"] = (
                f"{result.get('ambulance_id')} rerouted off shared corridor — "
                f"{holder_id} ({holder_pri}) keeps the shortest path."
            )
        else:
            conflict["status"] = "sequenced"
            conflict["yield_to"] = holder_id
            conflict["yield_to_label"] = holder_pri
            conflict["reason"] = (
                f"{result.get('ambulance_id')} follows {holder_id} ({holder_pri}) with a gap "
                f"on the shared corridor ({worst['km']} km overlap)."
            )
    elif lower:
        for item in lower:
            other = item["mission"]
            if float(item["delay_seconds"]) < DELAY_THRESHOLD_S:
                continue
            other_dest = other.get("hospital") or {}
            other_loc = get_ambulance(other.get("ambulance_id") or "") or {}
            o_origin = (
                float(other_loc.get("lat") or (remaining_path(other) or [(0, 0)])[0][0]),
                float(other_loc.get("lng") or (remaining_path(other) or [(0, 0)])[0][1]),
            )
            o_dest = (float(other_dest.get("lat") or 0), float(other_dest.get("lng") or 0))
            if not o_dest[0]:
                continue
            new_cells = path_cells(full)
            alt = _pick_alternate(
                o_origin,
                o_dest,
                new_cells,
                [full],
                item.get("bbox"),
                is_raining,
                float(other.get("transport_minutes") or 0) * 60,
            )
            extra = float((alt or {}).get("extra") or 10**9)
            if alt and alt.get("coords") and extra < float(item["delay_seconds"]):
                other["route"] = alt["coords"]
                other["conflict"] = {
                    "status": "rerouted",
                    "yield_to": result.get("ambulance_id"),
                    "yield_to_label": priority_label(priority),
                    "overlap_route": item.get("points") or [],
                    "reason": (
                        f"{other.get('ambulance_id')} rerouted — "
                        f"{result.get('ambulance_id')} ({priority_label(priority)}) has the corridor."
                    ),
                }
                save_mission(other)
                update_ambulance_paths(other.get("ambulance_id"), drop_path=alt["coords"])
                push_alert(
                    "staff",
                    "CORRIDOR YIELD",
                    other["conflict"]["reason"],
                    ambulance_id=other.get("ambulance_id"),
                    mission_id=other.get("id"),
                )
                conflict["status"] = "priority_hold"
                conflict["reason"] = other["conflict"]["reason"]
            else:
                conflict["status"] = "sequenced"
                conflict["reason"] = (
                    f"{other.get('ambulance_id')} yields sequencing to "
                    f"{result.get('ambulance_id')} ({priority_label(priority)})."
                )
        if conflict["status"] == "none":
            conflict["status"] = "priority_hold"
            conflict["reason"] = (
                f"{result.get('ambulance_id')} ({priority_label(priority)}) keeps the shortest path."
            )
    else:
        conflict["status"] = "sequenced"
        other_id = overlaps[0]["mission"].get("ambulance_id")
        conflict["reason"] = (
            f"{result.get('ambulance_id')} shares a corridor with {other_id}; sequenced with a gap."
        )

    if conflict.get("reason"):
        result["reason"] = f"{result.get('reason') or ''} {conflict['reason']}".strip()
    result["conflict"] = conflict
    return result


def corridor_snapshot() -> dict[str, Any]:
    from app.services.runtime_state import enrich_mission, list_active_missions

    missions = [enrich_mission(m) for m in list_active_missions()]
    extra_routes = []
    for m in missions:
        if not m:
            continue
        pickup = _normalize_path(m.get("pickup_route") or [])
        drop = _normalize_path(m.get("route") or m.get("drop_route") or [])
        conflict = m.get("conflict") or {}
        color = "#a855f7" if conflict.get("status") == "rerouted" else "#38bdf8"
        if m.get("phase") == "pickup" and pickup:
            extra_routes.append(
                {
                    "id": f"{m.get('id')}-pickup",
                    "label": f"{m.get('ambulance_id')} pickup",
                    "points": pickup,
                    "color": "#fb7185",
                    "kind": "pickup",
                }
            )
        if drop:
            extra_routes.append(
                {
                    "id": f"{m.get('id')}-drop",
                    "label": f"{m.get('ambulance_id')} → {m.get('hospital_name')}",
                    "points": drop,
                    "color": color,
                    "kind": "drop",
                }
            )
        if conflict.get("overlap_route"):
            extra_routes.append(
                {
                    "id": f"{m.get('id')}-overlap",
                    "label": "Shared corridor",
                    "points": conflict["overlap_route"],
                    "color": "#f59e0b",
                    "kind": "overlap",
                }
            )
    return {
        "posts": get_posts(),
        "sms": list_sms(),
        "missions": [
            {
                "id": m.get("id"),
                "ambulance_id": m.get("ambulance_id"),
                "hospital_name": m.get("hospital_name"),
                "phase": m.get("phase"),
                "priority": m.get("priority"),
                "priority_label": priority_label(int(m.get("priority") or 1)),
                "conflict": m.get("conflict") or {"status": "none"},
                "eta_minutes": m.get("eta_minutes"),
                "patient_name": m.get("patient_name"),
                "pickup_route": m.get("pickup_route") or [],
                "route": m.get("route") or m.get("drop_route") or [],
            }
            for m in missions
            if m
        ],
        "extra_routes": extra_routes,
        "alert_window_seconds": ALERT_WINDOW_S,
    }
