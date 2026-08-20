import os
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

import requests

# Ambulance privilege vs civilian driving time (skip signals / use shoulder).
EMERGENCY_ETA_FACTOR = 0.70
RAIN_ETA_FACTOR = 1.08

EMERGENCY_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "general_medical": {"types": ["BLS"], "fallback": ["ALS", "BLS"], "specialties": ["Emergency", "General"]},
    "cardiac": {"types": ["ALS"], "fallback": ["ALS", "BLS"], "specialties": ["Cardiac", "ICU", "Emergency"]},
    "respiratory": {"types": ["ALS"], "fallback": ["ALS", "BLS"], "specialties": ["ICU", "Emergency"]},
    "neurological": {"types": ["ALS"], "fallback": ["ALS", "BLS"], "specialties": ["Neuro", "Emergency", "ICU"]},
    "trauma": {"types": ["ALS"], "fallback": ["ALS", "BLS"], "specialties": ["Trauma", "Emergency"]},
    "obstetric": {"types": ["ALS"], "fallback": ["ALS", "BLS"], "specialties": ["Emergency", "ICU"]},
    "pediatric": {"types": ["NEONATAL_PEDIATRIC"], "fallback": ["ALS", "BLS"], "specialties": ["Pediatric", "Emergency"]},
    "bariatric_accessible": {"types": ["BARIATRIC_ACCESSIBLE"], "fallback": ["ALS", "BLS"], "specialties": ["Emergency", "General"]},
}


def dispatch_requirement(category: str | None, flags: dict[str, bool] | None = None, age_group: str | None = None, accessibility_need: bool = False) -> dict[str, Any]:
    """Resolve the caller's category into the safest capability requirement."""
    flags = flags or {}
    selected = (category or "general_medical").strip().lower()
    if accessibility_need:
        selected = "bariatric_accessible"
    elif age_group in ("infant", "child") and selected == "general_medical":
        selected = "pediatric"
    elif flags.get("cardiac"):
        selected = "cardiac"
    elif flags.get("epilepsy"):
        selected = "neurological"
    elif flags.get("pregnant"):
        selected = "obstetric"
    if selected not in EMERGENCY_REQUIREMENTS:
        selected = "general_medical"
    return {"category": selected, **EMERGENCY_REQUIREMENTS[selected]}


class DispatchOptimizer:
    def __init__(self):
        self._tomtom_available: bool | None = None

    def get_tomtom_route(
        self,
        origin: tuple,
        destination: tuple,
        api_key: str,
        emergency: bool = False,
        avoid_areas: list[tuple[float, float, float, float]] | None = None,
    ) -> Tuple[float, List[Tuple[float, float]]]:
        route_type = "shortest" if emergency else "fastest"
        traffic = "false" if emergency else "true"
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute/"
            f"{origin[0]},{origin[1]}:{destination[0]},{destination[1]}/json"
            f"?key={api_key}&traffic={traffic}&travelMode=car&routeType={route_type}"
        )
        if emergency:
            url += "&maxAlternatives=2"
        if avoid_areas:
            parts = []
            for south, west, north, east in avoid_areas[:3]:
                parts.append(f"rectangle:{south},{west}:{north},{east}")
            url += "&avoidAreas=" + quote(";".join(parts), safe=":;,")
        try:
            response = requests.get(url, timeout=8)
            data = response.json()
            routes = data.get("routes") or []
            if routes:
                chosen = routes[0]
                if emergency and len(routes) > 1:
                    chosen = min(
                        routes,
                        key=lambda r: float((r.get("summary") or {}).get("lengthInMeters") or 10**12),
                    )
                duration = float(chosen["summary"]["travelTimeInSeconds"])
                points = chosen["legs"][0]["points"]
                route_coords = [(pt["latitude"], pt["longitude"]) for pt in points]
                return duration, route_coords
            print("TomTom API Error:", data.get("error", data.get("detailedError", "unknown")))
        except Exception as e:
            print("Failed to contact TomTom API:", e)
        return float("inf"), []

    def get_osrm_route(
        self,
        origin: tuple,
        destination: tuple,
        emergency: bool = False,
    ) -> Tuple[float, List[Tuple[float, float]]]:
        alt = "true" if emergency else "false"
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            f"?overview=full&geometries=geojson&alternatives={alt}"
        )
        try:
            response = requests.get(url, timeout=8, headers={"User-Agent": "JEEVAN-dispatch/1.0"})
            data = response.json()
            routes = data.get("routes") or []
            if data.get("code") == "Ok" and routes:
                if emergency:
                    route = min(routes, key=lambda r: float(r.get("distance") or 10**12))
                else:
                    route = min(routes, key=lambda r: float(r.get("duration") or 10**12))
                duration = float(route["duration"])
                coords = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
                return duration, coords
        except Exception as e:
            print("Failed to contact OSRM:", e)
        return float("inf"), []

    def get_osrm_alternatives(
        self, origin: tuple, destination: tuple
    ) -> list[dict[str, Any]]:
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            "?overview=full&geometries=geojson&alternatives=true"
        )
        out: list[dict[str, Any]] = []
        try:
            response = requests.get(url, timeout=8, headers={"User-Agent": "JEEVAN-dispatch/1.0"})
            data = response.json()
            for route in data.get("routes") or []:
                coords = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
                out.append(
                    {
                        "duration": float(route.get("duration") or 0),
                        "distance": float(route.get("distance") or 0),
                        "coords": coords,
                    }
                )
        except Exception as e:
            print("Failed to contact OSRM alternatives:", e)
        return out

    def _tomtom_key(self) -> str | None:
        from app.core.config import settings

        key = (settings.TOMTOM_API_KEY or os.environ.get("TOMTOM_API_KEY") or "").strip()
        return key or None

    def _detect_tomtom(self) -> bool:
        """One-time probe: use TomTom only if a key exists and the API actually responds."""
        if self._tomtom_available is not None:
            return self._tomtom_available
        key = self._tomtom_key()
        if not key:
            self._tomtom_available = False
            return False
        duration, coords = self.get_tomtom_route((13.1344, 77.5693), (13.1168, 77.5819), key)
        self._tomtom_available = bool(coords) and duration != float("inf")
        return self._tomtom_available

    def _apply_emergency_eta(self, duration: float, is_raining: bool) -> float:
        if duration == float("inf"):
            return duration
        out = duration * EMERGENCY_ETA_FACTOR
        if is_raining:
            out *= RAIN_ETA_FACTOR
        return out

    def _route_direct(
        self,
        origin: tuple,
        destination: tuple,
        key: str | None,
        emergency: bool,
        is_raining: bool,
        avoid_areas: list[tuple[float, float, float, float]] | None,
    ):
        """Direct TomTom/OSRM routing used when the NetworkX graph is unavailable."""
        if key and self._detect_tomtom():
            duration, coords = self.get_tomtom_route(
                origin, destination, key, emergency=emergency, avoid_areas=avoid_areas
            )
            if duration != float("inf") and coords:
                if emergency:
                    return self._apply_emergency_eta(duration, is_raining), coords, "tomtom-direct"
                return duration, coords, "tomtom-live-traffic"
            self._tomtom_available = False

        duration, coords = self.get_osrm_route(origin, destination, emergency=emergency)
        if duration != float("inf") and coords:
            return (self._apply_emergency_eta(duration, is_raining) if emergency else duration), coords, "osrm-direct"
        return float("inf"), [], "none"

    def route_full(
        self,
        origin: tuple,
        destination: tuple,
        *,
        api_key: str | None = None,
        emergency: bool = True,
        is_raining: bool = False,
        avoid_areas: list[tuple[float, float, float, float]] | None = None,
        avoid_paths: list[list[tuple[float, float]]] | None = None,
        prefer: str = "fastest",
        enrich: bool = False,
    ) -> dict[str, Any]:
        """Primary router: NetworkX graph (Dijkstra) over live TomTom/OSRM roads.

        Returns distance + both shortest/fastest metrics and honours corridors
        already occupied by other ambulances via ``avoid_paths``.
        """
        from app.services import graph_router

        key = (api_key or "").strip() or self._tomtom_key()
        graph_key = key if (key and self._detect_tomtom()) else None

        if graph_router.available():
            try:
                g = graph_router.route(
                    origin,
                    destination,
                    api_key=graph_key,
                    avoid_paths=avoid_paths,
                    prefer=prefer,
                    enrich=enrich,
                )
            except Exception as exc:  # pragma: no cover - defensive
                print("graph_router failed, using direct routing:", exc)
                g = None
            if g and g.get("coords"):
                dur = g["duration"]
                if emergency:
                    dur = self._apply_emergency_eta(dur, is_raining)
                return {
                    "duration": dur,
                    "coords": g["coords"],
                    "source": g["source"],
                    "engine": "networkx",
                    "distance": g.get("distance"),
                    "shortest_km": g.get("shortest_km"),
                    "fastest_min": g.get("fastest_min"),
                    "occupied_hits": g.get("occupied_hits", 0),
                    "graph_nodes": g.get("graph_nodes"),
                }

        dur, coords, source = self._route_direct(origin, destination, key, emergency, is_raining, avoid_areas)
        return {
            "duration": dur,
            "coords": coords,
            "source": source,
            "engine": "direct",
            "distance": None,
            "shortest_km": None,
            "fastest_min": None,
            "occupied_hits": 0,
            "graph_nodes": None,
        }

    def _route(
        self,
        origin: tuple,
        destination: tuple,
        api_key: str | None = None,
        emergency: bool = True,
        is_raining: bool = False,
        avoid_areas: list[tuple[float, float, float, float]] | None = None,
        avoid_paths: list[list[tuple[float, float]]] | None = None,
        prefer: str = "fastest",
    ):
        res = self.route_full(
            origin,
            destination,
            api_key=api_key,
            emergency=emergency,
            is_raining=is_raining,
            avoid_areas=avoid_areas,
            avoid_paths=avoid_paths,
            prefer=prefer,
        )
        return res["duration"], res["coords"], res["source"]

    def compute_route(
        self,
        origin: tuple,
        destination: tuple,
        *,
        emergency: bool = True,
        is_raining: bool = False,
        avoid_areas: list[tuple[float, float, float, float]] | None = None,
        avoid_paths: list[list[tuple[float, float]]] | None = None,
        prefer: str = "fastest",
        enrich: bool = True,
    ) -> dict[str, Any]:
        return self.route_full(
            origin,
            destination,
            emergency=emergency,
            is_raining=is_raining,
            avoid_areas=avoid_areas,
            avoid_paths=avoid_paths,
            prefer=prefer,
            enrich=enrich,
        )

    def optimize_dispatch(self, incident_location: tuple, ambulances: List[Dict], requirement: dict[str, Any] | None = None) -> dict:
        if not ambulances:
            return {"ambulance_id": None, "route": []}

        requirement = requirement or dispatch_requirement(None)
        pick = self._pick_ambulance(
            incident_location,
            [
                {
                    **a,
                    "lat": a.get("lat") if a.get("lat") is not None else (a.get("location") or (0, 0))[0],
                    "lng": a.get("lng") if a.get("lng") is not None else (a.get("location") or (0, 0))[1],
                }
                for a in ambulances
            ],
            requirement=requirement,
        )
        unit = (pick or {}).get("ambulance") or ambulances[0]
        return {
            "ambulance_id": unit.get("id"),
            "route": (pick or {}).get("pickup_route") or [],
            "eta_seconds": (pick or {}).get("pickup_seconds") or 0,
            "emergency_category": requirement["category"],
            "assigned_ambulance_type": unit.get("ambulance_type"),
            "match_status": (pick or {}).get("match_status") or "unassigned",
        }

    def _peak_traffic_factor(self) -> float:
        hour = datetime.now().hour
        if 8 <= hour <= 11 or 17 <= hour <= 21:
            return 1.18
        if 12 <= hour <= 16:
            return 1.06
        return 1.0

    def _haversine_km(self, a: tuple, b: tuple) -> float:
        import math

        r = 6371.0
        lat1, lon1 = math.radians(a[0]), math.radians(a[1])
        lat2, lon2 = math.radians(b[0]), math.radians(b[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))

    def _pick_ambulance(
        self,
        incident_location: tuple,
        ambulances: List[Dict[str, Any]],
        is_raining: bool = False,
        requirement: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        requirement = requirement or dispatch_requirement(None)
        available = [a for a in ambulances if a.get("status") in (None, "available")]
        exact = [a for a in available if a.get("ambulance_type", "BLS") in requirement["types"]]
        fallback: list[dict[str, Any]] = []
        for ambulance_type in requirement["fallback"]:
            tier = [a for a in available if a.get("ambulance_type", "BLS") == ambulance_type]
            if tier:
                fallback = tier
                break
        if exact:
            pool, match_status = exact, "exact"
        elif fallback:
            pool, match_status = fallback, "fallback"
        else:
            pool, match_status = available, "last_resort"
        if not pool:
            return None
        shortlist = sorted(
            pool,
            key=lambda a: self._haversine_km((a["lat"], a["lng"]), incident_location),
        )[:3]

        best: dict[str, Any] | None = None
        for unit in shortlist:
            duration, coords, _source = self._route(
                (unit["lat"], unit["lng"]),
                incident_location,
                emergency=True,
                is_raining=is_raining,
            )
            if duration == float("inf") or not coords:
                coords = [(unit["lat"], unit["lng"]), incident_location]
                km = self._haversine_km((unit["lat"], unit["lng"]), incident_location)
                duration = max(60.0, km / 55.0 * 3600.0 * EMERGENCY_ETA_FACTOR)
            row = {
                "ambulance": unit,
                "pickup_seconds": duration if duration != float("inf") else 0,
                "pickup_route": coords,
                "match_status": match_status,
            }
            if best is None or row["pickup_seconds"] < best["pickup_seconds"]:
                best = row
        return best

    def optimize_hospital_dispatch(
        self,
        incident_location: tuple,
        hospitals: List[Dict[str, Any]],
        ambulances: List[Dict[str, Any]],
        is_raining: bool = False,
        requirement: dict[str, Any] | None = None,
    ) -> dict:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._detect_tomtom()
        requirement = requirement or dispatch_requirement(None)
        pickup = self._pick_ambulance(incident_location, ambulances, is_raining=is_raining, requirement=requirement)

        beds_available = [h for h in hospitals if int(h.get("available_beds") or 0) > 0]
        hospital_pool = beds_available or hospitals
        matching_hospitals = [
            h for h in hospital_pool
            if set(h.get("specializations") or []).intersection(requirement["specialties"])
        ]
        hospital_match_status = "specialty_match" if matching_hospitals else "capacity_fallback"
        hospital_pool = matching_hospitals or hospital_pool

        def score_hospital(hosp: Dict[str, Any]) -> dict[str, Any] | None:
            dest = (float(hosp["lat"]), float(hosp["lng"]))
            res = self.route_full(
                incident_location, dest, emergency=True, is_raining=is_raining, prefer="fastest"
            )
            duration, coords = res["duration"], res["coords"]
            if duration == float("inf") or not coords:
                return None
            pickup_s = float(pickup["pickup_seconds"]) if pickup else 0.0
            effective = pickup_s + duration
            return {
                "hospital": hosp,
                "route": coords,
                "raw_seconds": duration,
                "transport_seconds": duration,
                "pickup_seconds": pickup_s,
                "eta_seconds": effective,
                "source": res["source"],
                "engine": res.get("engine"),
                "shortest_km": res.get("shortest_km"),
                "fastest_min": res.get("fastest_min"),
                "graph_nodes": res.get("graph_nodes"),
            }

        scored: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(score_hospital, hosp) for hosp in hospital_pool]
            for fut in as_completed(futures):
                row = fut.result()
                if row:
                    scored.append(row)

        best: dict[str, Any] | None = min(scored, key=lambda r: r["eta_seconds"]) if scored else None

        if best is None:
            nearest = min(
                hospital_pool,
                key=lambda h: (h["lat"] - incident_location[0]) ** 2 + (h["lng"] - incident_location[1]) ** 2,
            )
            best = {
                "hospital": nearest,
                "route": [incident_location, (nearest["lat"], nearest["lng"])],
                "raw_seconds": 720 * EMERGENCY_ETA_FACTOR,
                "transport_seconds": 720 * EMERGENCY_ETA_FACTOR,
                "pickup_seconds": float(pickup["pickup_seconds"]) if pickup else 0.0,
                "eta_seconds": 720 * EMERGENCY_ETA_FACTOR,
                "source": "straight-line-fallback",
            }

        assigned = pickup["ambulance"] if pickup else None
        ranked = sorted(scored, key=lambda r: r["eta_seconds"]) if scored else [best]
        runner_up = ranked[1]["eta_seconds"] if len(ranked) > 1 else best["eta_seconds"] * 1.12
        gap = max(runner_up - best["eta_seconds"], 0)
        confidence = int(min(97, max(62, 70 + (gap / max(best["eta_seconds"], 1)) * 120)))

        hospital = dict(best["hospital"])
        eta = int(round(best["eta_seconds"]))
        pickup_min = round(float(best.get("pickup_seconds") or 0) / 60, 1)
        transport_min = round(float(best.get("transport_seconds") or eta) / 60, 1)
        specs = ", ".join(hospital.get("specializations") or [])
        amb_label = (assigned or {}).get("label") or (assigned or {}).get("id") or "nearest unit"
        match_status = (pickup or {}).get("match_status") or "unassigned"
        engine = best.get("engine") or "direct"
        shortest_km = best.get("shortest_km")
        fastest_min = best.get("fastest_min")
        engine_note = (
            f"NetworkX Dijkstra over live TomTom traffic"
            if engine == "networkx"
            else "Direct TomTom/OSRM routing"
        )
        metric_note = ""
        if shortest_km is not None and fastest_min is not None:
            metric_note = f" Graph compared shortest {shortest_km} km vs fastest {fastest_min} min."
        reason = (
            f"{engine_note}: emergency corridor (traffic delays waived). "
            f"{(assigned or {}).get('type_label') or 'Ambulance'} {amb_label} assigned ({match_status.replace('_', ' ')} match). "
            f"{hospital.get('name')} is the fastest destination "
            f"({pickup_min} min pickup + {transport_min} min to hospital).{metric_note}"
            + (f" Specialties: {specs}." if specs else "")
        )
        return {
            "ambulance_id": assigned["id"] if assigned else None,
            "ambulance": assigned,
            "emergency_category": requirement["category"],
            "required_ambulance_types": requirement["types"],
            "assigned_ambulance_type": (assigned or {}).get("ambulance_type"),
            "assigned_ambulance_type_label": (assigned or {}).get("type_label"),
            "match_status": match_status,
            "fallback_reason": (
                None if match_status == "exact" else "No available exact-match unit; the safest available dispatch option was selected."
            ),
            "hospital": hospital,
            "hospital_id": hospital.get("id"),
            "hospital_name": hospital.get("name"),
            "route": best["route"],
            "pickup_route": (pickup or {}).get("pickup_route") or [],
            "eta_seconds": eta,
            "eta_minutes": round(eta / 60, 1),
            "pickup_minutes": pickup_min,
            "transport_minutes": transport_min,
            "confidence": confidence,
            "reason": reason,
            "constraints": {
                "routing": "emergency-shortest",
                "traffic": "waived",
                "provider": best["source"],
                "engine": engine,
                "shortest_km": shortest_km,
                "fastest_min": fastest_min,
                "graph_nodes": best.get("graph_nodes"),
                "hospital_match_status": hospital_match_status,
            },
            "candidates": [
                {
                    "id": r["hospital"]["id"],
                    "name": r["hospital"]["name"],
                    "eta_minutes": round(r["eta_seconds"] / 60, 1),
                    "pickup_minutes": round(float(r.get("pickup_seconds") or 0) / 60, 1),
                    "transport_minutes": round(float(r.get("transport_seconds") or 0) / 60, 1),
                    "specializations": r["hospital"].get("specializations") or [],
                    "available_beds": r["hospital"].get("available_beds"),
                }
                for r in ranked[:5]
            ],
        }


optimizer = DispatchOptimizer()


def get_optimal_ambulance(
    incident_lat: float,
    incident_lng: float,
    available_ambulances: list,
    emergency_category: str | None = None,
    flags: dict[str, bool] | None = None,
    age_group: str | None = None,
    accessibility_need: bool = False,
) -> dict:
    return optimizer.optimize_dispatch(
        (incident_lat, incident_lng),
        available_ambulances,
        dispatch_requirement(emergency_category, flags, age_group, accessibility_need),
    )


def get_optimal_hospital_dispatch(
    incident_lat: float,
    incident_lng: float,
    hospitals: list,
    ambulances: list,
    is_raining: bool = False,
    emergency_category: str | None = None,
    flags: dict[str, bool] | None = None,
    age_group: str | None = None,
    accessibility_need: bool = False,
) -> dict:
    return optimizer.optimize_hospital_dispatch(
        (incident_lat, incident_lng), hospitals, ambulances, is_raining,
        dispatch_requirement(emergency_category, flags, age_group, accessibility_need),
    )


def _path_km(coords: list[tuple[float, float]] | None) -> float:
    if not coords or len(coords) < 2:
        return 0.0
    km = 0.0
    for i in range(len(coords) - 1):
        km += optimizer._haversine_km(coords[i], coords[i + 1])
    return round(km, 2)


def simulate_custom_route(
    ambulance: dict[str, Any],
    pickup: tuple[float, float],
    destination: tuple[float, float],
    *,
    is_raining: bool = False,
    prefer: str = "fastest",
) -> dict[str, Any]:
    """Dry-run route calculation for admin simulation — does not mutate fleet or missions."""
    amb_loc = (float(ambulance["lat"]), float(ambulance["lng"]))
    pickup_res = optimizer.compute_route(
        amb_loc, pickup, emergency=True, is_raining=is_raining, prefer=prefer, enrich=True
    )
    drop_res = optimizer.compute_route(
        pickup, destination, emergency=True, is_raining=is_raining, prefer=prefer, enrich=True
    )

    pickup_sec = float(pickup_res.get("duration") or 0)
    drop_sec = float(drop_res.get("duration") or 0)
    if pickup_sec == float("inf"):
        pickup_sec = 0.0
    if drop_sec == float("inf"):
        drop_sec = 0.0
    total_sec = pickup_sec + drop_sec

    pickup_coords = pickup_res.get("coords") or []
    drop_coords = drop_res.get("coords") or []
    pickup_km = _path_km(pickup_coords)
    drop_km = _path_km(drop_coords)
    peak = optimizer._peak_traffic_factor()

    engine = drop_res.get("engine") or pickup_res.get("engine") or "direct"
    provider = drop_res.get("source") or pickup_res.get("source") or "unknown"
    shortest_km = drop_res.get("shortest_km")
    fastest_min = drop_res.get("fastest_min")

    weather_note = "Rain detected — ETA adjusted (+8%)" if is_raining else "Clear weather at pickup"
    if 8 <= datetime.now().hour <= 11 or 17 <= datetime.now().hour <= 21:
        traffic_note = "Peak traffic window — emergency corridor bypasses delays"
    elif 12 <= datetime.now().hour <= 16:
        traffic_note = "Moderate traffic — emergency corridor active"
    else:
        traffic_note = "Light traffic conditions"

    metric_note = ""
    if shortest_km is not None and fastest_min is not None:
        metric_note = f" Graph compared shortest {shortest_km} km vs fastest {fastest_min} min."

    pickup_min = round(pickup_sec / 60, 1)
    transport_min = round(drop_sec / 60, 1)
    eta_min = round(total_sec / 60, 1)

    reason = (
        f"Admin simulation ({engine} via {provider}): "
        f"{ambulance.get('label') or ambulance.get('id')} → pickup {pickup_min} min ({pickup_km} km), "
        f"then transport {transport_min} min ({drop_km} km). "
        f"{weather_note}. {traffic_note}.{metric_note}"
    )

    return {
        "simulation": True,
        "label": "Admin Simulation",
        "ambulance_id": ambulance.get("id"),
        "ambulance": ambulance,
        "pickup_route": pickup_coords,
        "route": drop_coords,
        "pickup_minutes": pickup_min,
        "transport_minutes": transport_min,
        "eta_minutes": eta_min,
        "eta_seconds": int(round(total_sec)),
        "pickup_seconds": int(round(pickup_sec)),
        "transport_seconds": int(round(drop_sec)),
        "pickup_distance_km": pickup_km,
        "transport_distance_km": drop_km,
        "total_distance_km": round(pickup_km + drop_km, 2),
        "is_raining": is_raining,
        "reason": reason,
        "confidence": 100,
        "constraints": {
            "routing": "emergency-shortest",
            "traffic": "waived",
            "provider": provider,
            "engine": engine,
            "shortest_km": shortest_km,
            "fastest_min": fastest_min,
            "peak_traffic_factor": peak,
            "rain_adjustment": is_raining,
            "weather": weather_note,
            "road_conditions": traffic_note,
            "prefer": prefer,
            "graph_nodes": drop_res.get("graph_nodes"),
            "occupied_hits": (pickup_res.get("occupied_hits") or 0) + (drop_res.get("occupied_hits") or 0),
        },
    }
