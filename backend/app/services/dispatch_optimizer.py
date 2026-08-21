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


def _hospital_spec_set(hospital: dict[str, Any]) -> set[str]:
    specs = {str(s) for s in (hospital.get("specializations") or []) if s}
    if hospital.get("icu_available"):
        specs.add("ICU")
    return specs


def filter_eligible_hospitals(
    hospitals: list[dict[str, Any]],
    requirement: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Same matching used by live dispatch: beds, then required specialties, then fallback."""
    requirement = requirement or dispatch_requirement(None)
    open_ok = [
        h
        for h in hospitals
        if (h.get("status") or "operational") not in ("closed", "offline")
        and h.get("emergency_available", True)
    ]
    pool = open_ok or list(hospitals)
    beds_available = [h for h in pool if int(h.get("available_beds") or 0) > 0]
    hospital_pool = beds_available or pool
    matching = [
        h for h in hospital_pool if _hospital_spec_set(h).intersection(requirement["specialties"])
    ]
    preferred_keys = {
        s for s in ("Cardiac", "Neuro", "Trauma", "ICU", "Pediatric") if s in requirement["specialties"]
    }
    if matching and preferred_keys:
        preferred = [h for h in matching if _hospital_spec_set(h).intersection(preferred_keys)]
        if preferred:
            matching = preferred
    status = "specialty_match" if matching else "capacity_fallback"
    return (matching or hospital_pool), status


def nearest_eligible_hospital(
    origin: tuple[float, float],
    hospitals: list[dict[str, Any]],
    requirement: dict[str, Any] | None = None,
    *,
    is_raining: bool = False,
    traffic_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Fastest routed hospital among eligible facilities — not raw geographic nearest."""
    requirement = requirement or dispatch_requirement(None)
    pool, match_status = filter_eligible_hospitals(hospitals, requirement)
    if not pool:
        return None
    scored: list[dict[str, Any]] = []
    for hosp in pool:
        dest = (float(hosp["lat"]), float(hosp["lng"]))
        res = optimizer.route_full(
            origin,
            dest,
            emergency=True,
            is_raining=is_raining,
            prefer="fastest",
            traffic_points=traffic_points,
        )
        duration, coords = res["duration"], res["coords"]
        if duration == float("inf") or not coords:
            continue
        scored.append(
            {
                "hospital": hosp,
                "route": coords,
                "raw_seconds": duration,
                "transport_seconds": duration,
                "eta_seconds": duration,
                "source": res.get("source"),
                "engine": res.get("engine"),
                "alternatives": res.get("alternatives") or [],
                "match_status": match_status,
            }
        )
    if not scored:
        nearest = min(
            pool,
            key=lambda h: (float(h["lat"]) - origin[0]) ** 2 + (float(h["lng"]) - origin[1]) ** 2,
        )
        return {
            "hospital": nearest,
            "route": [origin, (nearest["lat"], nearest["lng"])],
            "raw_seconds": 720 * EMERGENCY_ETA_FACTOR,
            "transport_seconds": 720 * EMERGENCY_ETA_FACTOR,
            "eta_seconds": 720 * EMERGENCY_ETA_FACTOR,
            "source": "straight-line-fallback",
            "engine": "direct",
            "alternatives": [],
            "match_status": match_status,
        }
    best = min(scored, key=lambda r: r["eta_seconds"])
    best["ranked"] = sorted(scored, key=lambda r: r["eta_seconds"])
    return best


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

    def _direct_alternatives(
        self,
        origin: tuple,
        destination: tuple,
        chosen_coords: list,
        chosen_dur: float,
        source: str,
        emergency: bool,
        is_raining: bool,
    ) -> list[dict[str, Any]]:
        selected = {
            "rank": 1,
            "label": "Route 1",
            "coords": chosen_coords or [],
            "duration": chosen_dur if chosen_dur != float("inf") else 0.0,
            "distance": _path_km(chosen_coords) * 1000.0 if chosen_coords else 0.0,
            "kind": "selected",
            "path_sig": "",
        }
        extras: list[dict[str, Any]] = []
        seen = {tuple((round(p[0], 4), round(p[1], 4)) for p in (chosen_coords or [])[:8])}
        for row in self.get_osrm_alternatives(origin, destination):
            coords = row.get("coords") or []
            key = tuple((round(p[0], 4), round(p[1], 4)) for p in coords[:8])
            if not coords or key in seen:
                continue
            seen.add(key)
            dur = float(row.get("duration") or 0.0)
            if emergency:
                dur = self._apply_emergency_eta(dur, is_raining)
            extras.append(
                {
                    "coords": coords,
                    "duration": dur,
                    "distance": float(row.get("distance") or 0.0),
                    "kind": "provider",
                }
            )
        extras.sort(key=lambda r: r["duration"] or 10**12)
        out = [selected]
        for i, row in enumerate(extras[:2], start=2):
            out.append({**row, "rank": i, "label": f"Route {i}", "path_sig": ""})
        return out

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
        traffic_points: list[dict[str, Any]] | None = None,
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
                    traffic_points=traffic_points,
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
                    "traffic_hits": g.get("traffic_hits", 0),
                    "sim_traffic": g.get("sim_traffic") or [],
                    "path_sig": g.get("path_sig") or "",
                    "graph_nodes": g.get("graph_nodes"),
                    "alternatives": [
                        {
                            **alt,
                            "duration": self._apply_emergency_eta(float(alt.get("duration") or 0), is_raining)
                            if emergency
                            else float(alt.get("duration") or 0),
                        }
                        for alt in (g.get("alternatives") or [])
                    ],
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
            "traffic_hits": 0,
            "sim_traffic": [],
            "path_sig": "",
            "graph_nodes": None,
            "alternatives": self._direct_alternatives(origin, destination, coords, dur, source, emergency, is_raining),
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
        traffic_points: list[dict[str, Any]] | None = None,
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
            traffic_points=traffic_points,
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

        hospital_pool, hospital_match_status = filter_eligible_hospitals(hospitals, requirement)

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
    traffic_points: list[dict[str, Any]] | None = None,
    previous_drop_sig: str | None = None,
    previous_pickup_sig: str | None = None,
    hospital: dict[str, Any] | None = None,
    emergency_category: str | None = None,
    flags: dict[str, bool] | None = None,
    hospital_rerouted: bool = False,
) -> dict[str, Any]:
    """Dry-run route calculation for admin simulation — does not mutate fleet or missions."""
    from app.services.graph_router import path_signature, _taps_label

    requirement = dispatch_requirement(emergency_category, flags)
    hospital_match_ok = True
    hospital_match_status = "unassigned"
    if hospital:
        pool, hospital_match_status = filter_eligible_hospitals([hospital], requirement)
        hospital_match_ok = hospital_match_status == "specialty_match"

    amb_loc = (float(ambulance["lat"]), float(ambulance["lng"]))
    points = [p for p in (traffic_points or []) if p]
    pickup_res = optimizer.compute_route(
        amb_loc,
        pickup,
        emergency=True,
        is_raining=is_raining,
        prefer=prefer,
        enrich=True,
        traffic_points=points or None,
    )
    drop_res = optimizer.compute_route(
        pickup,
        destination,
        emergency=True,
        is_raining=is_raining,
        prefer=prefer,
        enrich=True,
        traffic_points=points or None,
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
    drop_sig = drop_res.get("path_sig") or path_signature(drop_coords)
    pickup_sig = pickup_res.get("path_sig") or path_signature(pickup_coords)
    rerouted = bool(
        points
        and (
            (previous_drop_sig and previous_drop_sig != drop_sig)
            or (previous_pickup_sig and previous_pickup_sig != pickup_sig)
        )
    )

    sim_traffic = list(drop_res.get("sim_traffic") or []) + list(pickup_res.get("sim_traffic") or [])
    merged: dict[tuple[float, float, int], dict[str, Any]] = {}
    for row in sim_traffic:
        key = (round(float(row.get("lat") or 0), 5), round(float(row.get("lng") or 0), 5), int(row.get("taps") or 1))
        prev = merged.get(key)
        if prev:
            prev["on_route"] = bool(prev.get("on_route") or row.get("on_route"))
            if prev["on_route"]:
                prev["status"] = "on_route"
        else:
            merged[key] = dict(row)
    sim_traffic = list(merged.values())
    on_route_count = sum(1 for row in sim_traffic if row.get("on_route"))
    traffic_hits = int(pickup_res.get("traffic_hits") or 0) + int(drop_res.get("traffic_hits") or 0)

    weather_note = "Rain detected — ETA adjusted (+8%)" if is_raining else "Clear weather at pickup"
    if points:
        densest = max((int(p.get("taps") or 1) for p in points), default=1)
        traffic_note = (
            f"Simulation traffic: {len(points)} hotspot(s), densest {_taps_label(densest).lower()}. "
            f"{traffic_hits} road cell(s) on the chosen path penalized."
        )
        if rerouted:
            traffic_note += " Faster alternative selected after cost increase."
        elif traffic_hits:
            traffic_note += " Current path still fastest; ETA updated."
    elif 8 <= datetime.now().hour <= 11 or 17 <= datetime.now().hour <= 21:
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
    priority = _sim_priority(emergency_category, flags)
    from app.services.corridor import priority_label as corridor_priority_label

    reason = (
        f"Admin simulation ({engine} via {provider}): "
        f"{ambulance.get('label') or ambulance.get('id')} → pickup {pickup_min} min ({pickup_km} km), "
        f"then transport {transport_min} min ({drop_km} km). "
        f"{weather_note}. {traffic_note}.{metric_note}"
    )

    alts = []
    for alt in drop_res.get("alternatives") or []:
        coords = alt.get("coords") or []
        dur = float(alt.get("duration") or 0.0)
        dist_m = float(alt.get("distance") or 0.0)
        dist_km = round(dist_m / 1000.0, 2) if dist_m else _path_km(coords)
        alts.append(
            {
                "rank": alt.get("rank"),
                "label": alt.get("label") or f"Route {alt.get('rank')}",
                "kind": alt.get("kind"),
                "coords": coords,
                "eta_minutes": round(dur / 60.0, 1) if dur else None,
                "distance_km": dist_km,
            }
        )
    if not alts and drop_coords:
        alts = [
            {
                "rank": 1,
                "label": "Route 1",
                "kind": "selected",
                "coords": drop_coords,
                "eta_minutes": transport_min,
                "distance_km": drop_km,
            }
        ]

    algorithm = _algorithm_label(engine, provider, prefer)
    traffic_summary = _traffic_summary(points, traffic_hits, rerouted)
    conditions = _decision_conditions(
        prefer=prefer,
        traffic_hits=traffic_hits,
        occupied_hits=int((pickup_res.get("occupied_hits") or 0) + (drop_res.get("occupied_hits") or 0)),
        is_raining=is_raining,
        simulated_traffic=bool(points),
        hospital_ok=hospital_match_ok,
        ambulance_ok=True,
        rerouted=rerouted,
        hospital_rerouted=hospital_rerouted,
    )
    if hospital_rerouted:
        decision = (
            "Critical danger rating: destination switched to the nearest eligible hospital "
            "and Route 1 is the lowest valid emergency travel cost to that facility."
        )
    elif rerouted:
        decision = "Route 1 currently provides the lowest valid emergency travel cost after simulated traffic increased the previous path's cost."
    else:
        decision = "Route 1 currently provides the lowest valid emergency travel cost."

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
        "rerouted": rerouted,
        "path_sig_drop": drop_sig,
        "path_sig_pickup": pickup_sig,
        "sim_traffic": sim_traffic,
        "traffic_hits": traffic_hits,
        "traffic_on_route": on_route_count,
        "candidate_routes": alts,
        "algorithm": algorithm,
        "decision": {
            "selected_route": "Route 1",
            "algorithm": algorithm,
            "eta_minutes": eta_min,
            "distance_km": round(pickup_km + drop_km, 2),
            "traffic": traffic_summary,
            "road_conditions": traffic_note,
            "conditions_met": conditions,
            "decision": decision,
        },
        "hospital": hospital,
        "hospital_id": (hospital or {}).get("id"),
        "hospital_name": (hospital or {}).get("name"),
        "emergency_category": requirement["category"],
        "hospital_match_status": hospital_match_status,
        "hospital_rerouted": hospital_rerouted,
        "priority": priority,
        "priority_label": corridor_priority_label(priority),
        "constraints": {
            "routing": "emergency-shortest",
            "traffic": "simulated" if points else "waived",
            "provider": provider,
            "engine": engine,
            "algorithm": algorithm,
            "shortest_km": shortest_km,
            "fastest_min": fastest_min,
            "peak_traffic_factor": peak,
            "rain_adjustment": is_raining,
            "weather": weather_note,
            "road_conditions": traffic_note,
            "prefer": prefer,
            "graph_nodes": drop_res.get("graph_nodes"),
            "occupied_hits": (pickup_res.get("occupied_hits") or 0) + (drop_res.get("occupied_hits") or 0),
            "sim_traffic_points": len(points),
            "rerouted": rerouted,
            "hospital_match_status": hospital_match_status,
        },
    }


def _algorithm_label(engine: str, provider: str, prefer: str) -> str:
    if engine == "networkx":
        metric = "fastest travel time" if prefer != "shortest" else "shortest distance"
        return f"NetworkX Dijkstra over live TomTom/OSRM roads ({metric})"
    if "tomtom" in (provider or ""):
        return "Direct TomTom routing"
    if "osrm" in (provider or ""):
        return "Direct OSRM routing"
    return provider or engine or "routing engine"


def _traffic_summary(points: list, traffic_hits: int, rerouted: bool) -> str:
    from app.services.graph_router import _taps_label

    if not points:
        return "No simulated traffic · emergency corridor (live delays waived)"
    densest = max((int(p.get("taps") or 1) for p in points), default=1)
    label = _taps_label(densest)
    extra = "rerouted" if rerouted else f"{traffic_hits} cell(s) on selected path"
    return f"Simulation · densest {label.lower()} · {extra}"


def _decision_conditions(
    *,
    prefer: str,
    traffic_hits: int,
    occupied_hits: int,
    is_raining: bool,
    simulated_traffic: bool,
    hospital_ok: bool,
    ambulance_ok: bool,
    rerouted: bool,
    hospital_rerouted: bool,
) -> list[str]:
    items: list[str] = []
    if prefer == "shortest":
        items.append("Shortest distance path among calculated candidates")
    else:
        items.append("Lowest predicted travel time among calculated candidates")
    if simulated_traffic:
        if traffic_hits:
            items.append(f"Simulated congestion applied to {traffic_hits} selected-path cell(s)")
        else:
            items.append("No major simulated blockage on the selected path")
        if rerouted:
            items.append("Previous path cost increased; a faster calculated alternative was selected")
    else:
        items.append("Emergency corridor active (live civilian traffic delays waived)")
    if occupied_hits == 0:
        items.append("No occupied ambulance corridor conflict")
    else:
        items.append("Occupied-corridor penalty applied in the graph")
    if hospital_ok:
        items.append("Hospital requirements satisfied")
    else:
        items.append("Assigned hospital kept; specialty pool used capacity fallback")
    if ambulance_ok:
        items.append("Ambulance eligible for this simulation")
    if is_raining:
        items.append("Rain ETA adjustment applied (+8%)")
    if hospital_rerouted:
        items.append("Critical danger rating: nearest eligible hospital selected")
    return items


# Priority multipliers for joint ETA cost. Higher urgency weighs more, but does not
# invent routes — it only ranks real engine candidates.
_DUAL_PRI_WEIGHT = {5: 1.55, 4: 1.32, 3: 1.14, 2: 1.06, 1: 1.0}
_STARVE_S = 90.0  # matches corridor.DELAY_THRESHOLD_S
_OVERLAP_COST = 0.9
_TRAFFIC_SHARE_COST = 35.0  # seconds added per shared congested cell


def _sim_priority(category: str | None, flags: dict[str, Any] | None) -> int:
    """Map simulation emergency type + flags onto the live corridor priority scale."""
    from app.services.corridor import mission_priority

    flags = dict(flags or {})
    cat = (category or "general_medical").strip().lower()
    if cat == "cardiac":
        flags["cardiac"] = True
    elif cat == "obstetric":
        flags["pregnant"] = True
    elif cat in ("neurological",):
        flags["epilepsy"] = True
    pri = mission_priority(flags)
    if cat == "trauma":
        return max(5, pri)
    if cat == "respiratory":
        return max(4, pri)
    if cat == "pediatric":
        return max(3, pri)
    return pri


def _full_sim_path(sim: dict[str, Any]) -> list[tuple[float, float]]:
    pickup = [tuple(p) for p in (sim.get("pickup_route") or []) if p]
    drop = [tuple(p) for p in (sim.get("route") or []) if p]
    return pickup + drop


def _drop_candidates(sim: dict[str, Any]) -> list[dict[str, Any]]:
    alts = list(sim.get("candidate_routes") or [])
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    from app.services.graph_router import path_signature

    for alt in alts:
        coords = [tuple(p) for p in (alt.get("coords") or []) if p]
        if len(coords) < 2:
            continue
        sig = str(alt.get("path_sig") or path_signature(coords))
        if sig in seen:
            continue
        seen.add(sig)
        dur_s = float(alt.get("duration") or 0.0)
        if not dur_s and alt.get("eta_minutes") is not None:
            dur_s = float(alt["eta_minutes"]) * 60.0
        dist_km = alt.get("distance_km")
        if dist_km is None:
            dist_m = float(alt.get("distance") or 0.0)
            dist_km = round(dist_m / 1000.0, 2) if dist_m else _path_km(coords)
        rank = int(alt.get("rank") or (len(out) + 1))
        out.append(
            {
                "id": f"R{rank}",
                "label": alt.get("label") or f"Route {rank}",
                "rank": rank,
                "coords": coords,
                "duration_s": dur_s,
                "eta_minutes": round(dur_s / 60.0, 1) if dur_s else alt.get("eta_minutes"),
                "distance_km": dist_km,
                "kind": alt.get("kind") or "provider",
                "path_sig": sig,
            }
        )
    if not out:
        coords = [tuple(p) for p in (sim.get("route") or []) if p]
        if len(coords) >= 2:
            dur_s = float(sim.get("transport_seconds") or 0)
            out.append(
                {
                    "id": "R1",
                    "label": "Route 1",
                    "rank": 1,
                    "coords": coords,
                    "duration_s": dur_s,
                    "eta_minutes": sim.get("transport_minutes"),
                    "distance_km": sim.get("transport_distance_km"),
                    "kind": "selected",
                    "path_sig": sim.get("path_sig_drop") or path_signature(coords),
                }
            )
    return out


def _pack_engine_drop(drop_res: dict[str, Any], rank: int, kind: str) -> dict[str, Any] | None:
    coords = [tuple(p) for p in (drop_res.get("coords") or []) if p]
    if len(coords) < 2:
        return None
    from app.services.graph_router import path_signature

    dur_s = float(drop_res.get("duration") or 0.0)
    dist_m = float(drop_res.get("distance") or 0.0)
    return {
        "id": f"R{rank}",
        "label": f"Route {rank} (corridor-aware)",
        "rank": rank,
        "coords": coords,
        "duration_s": dur_s,
        "eta_minutes": round(dur_s / 60.0, 1) if dur_s else None,
        "distance_km": round(dist_m / 1000.0, 2) if dist_m else _path_km(coords),
        "kind": kind,
        "path_sig": drop_res.get("path_sig") or path_signature(coords),
        "traffic_hits": int(drop_res.get("traffic_hits") or 0),
        "occupied_hits": int(drop_res.get("occupied_hits") or 0),
    }


def _append_unique_drop(cands: list[dict[str, Any]], extra: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not extra:
        return cands
    seen = {c["path_sig"] for c in cands if c.get("path_sig")}
    if extra.get("path_sig") in seen:
        return cands
    extra = dict(extra)
    extra["rank"] = len(cands) + 1
    extra["id"] = f"R{extra['rank']}"
    if extra.get("kind") == "corridor_avoid":
        extra["label"] = f"Route {extra['rank']} (corridor-aware)"
    cands.append(extra)
    return cands


def _path_near_traffic(path: list[tuple[float, float]], points: list[dict[str, Any]], radius_m: float = 120.0) -> int:
    if not path or not points:
        return 0
    hits = 0
    for pt in points:
        try:
            lat, lng = float(pt["lat"]), float(pt["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        if any(optimizer._haversine_km((lat, lng), node) * 1000.0 <= radius_m for node in path):
            hits += 1
    return hits


def _apply_selected_drop(sim: dict[str, Any], drop: dict[str, Any], *, pickup_min: float) -> dict[str, Any]:
    """Copy a single-mission sim result onto a jointly chosen drop alternative."""
    out = dict(sim)
    coords = drop.get("coords") or []
    drop_s = float(drop.get("duration_s") or 0.0)
    drop_min = round(drop_s / 60.0, 1) if drop_s else float(drop.get("eta_minutes") or 0.0)
    pickup_s = float(sim.get("pickup_seconds") or pickup_min * 60.0)
    total_min = round(pickup_min + drop_min, 1)
    drop_km = float(drop.get("distance_km") or _path_km(coords) or 0.0)
    pickup_km = float(sim.get("pickup_distance_km") or 0.0)
    out["route"] = coords
    out["transport_minutes"] = drop_min
    out["transport_seconds"] = int(round(drop_s or drop_min * 60.0))
    out["transport_distance_km"] = drop_km
    out["eta_minutes"] = total_min
    out["eta_seconds"] = int(round((pickup_s / 60.0 + drop_min) * 60.0))
    out["total_distance_km"] = round(pickup_km + drop_km, 2)
    out["path_sig_drop"] = drop.get("path_sig")
    out["selected_route_id"] = drop.get("id")
    out["selected_route_label"] = drop.get("label")
    decision = dict(out.get("decision") or {})
    decision["selected_route"] = drop.get("label") or "Route 1"
    decision["eta_minutes"] = total_min
    decision["distance_km"] = out["total_distance_km"]
    out["decision"] = decision
    return out


def _combo_cost(
    *,
    eta1_s: float,
    eta2_s: float,
    p1: int,
    p2: int,
    overlap_delay_s: float,
    overlap_km: float,
    delay1_s: float,
    delay2_s: float,
    shared_traffic: int,
) -> float:
    w1 = _DUAL_PRI_WEIGHT.get(int(p1), 1.0)
    w2 = _DUAL_PRI_WEIGHT.get(int(p2), 1.0)
    cost = eta1_s * w1 + eta2_s * w2
    cost += max(0.0, overlap_delay_s) * _OVERLAP_COST
    cost += shared_traffic * _TRAFFIC_SHARE_COST
    # Traffic starvation: delaying a mission ≥90s while sharing a corridor is costly.
    # Higher (or equal) clinical urgency is protected more strongly.
    if overlap_km > 0:
        if delay1_s >= _STARVE_S:
            cost += delay1_s * (1.45 if p1 >= p2 else 0.45)
        if delay2_s >= _STARVE_S:
            cost += delay2_s * (1.45 if p2 >= p1 else 0.45)
    # Clinical override: slowing the more urgent mission is expensive even without overlap.
    if p1 > p2:
        cost += max(0.0, delay1_s) * 2.1
    elif p2 > p1:
        cost += max(0.0, delay2_s) * 2.1
    return cost


def _dual_why(
    best: dict[str, Any],
    selfish: dict[str, Any],
    runner: dict[str, Any] | None,
    p1: int,
    p2: int,
    lab1: str,
    lab2: str,
) -> tuple[list[str], str, str, str]:
    """Build actual-value bullets. Returns (why, starvation, conflict, strategy)."""
    why: list[str] = []
    overlap = float(best.get("overlap_km") or 0)
    selfish_overlap = float(selfish.get("overlap_km") or 0)
    d1 = float(best.get("delay1_s") or 0)
    d2 = float(best.get("delay2_s") or 0)
    sd1 = float(selfish.get("delay1_s") or 0)
    sd2 = float(selfish.get("delay2_s") or 0)

    if overlap <= 0.25 and selfish_overlap > 0.5:
        why.append(
            f"Avoids both ambulances competing for the same corridor "
            f"(independent fastest pair shared {selfish_overlap:.2f} km; selected pair {overlap:.2f} km)"
        )
        conflict = "avoided"
    elif overlap <= 0:
        why.append("Routes do not share corridor cells")
        conflict = "none"
    else:
        why.append(
            f"Shared corridor remains {overlap:.2f} km "
            f"(~{int(round(float(best.get('overlap_delay_s') or 0)))} s predicted interaction delay)"
        )
        conflict = "shared"

    if best.get("shared_traffic"):
        why.append(
            f"Reduces predicted congestion: {best['shared_traffic']} simulated hotspot(s) sit on both selected paths"
        )
    elif selfish.get("shared_traffic") and not best.get("shared_traffic"):
        why.append("Selected pair no longer stacks both missions on the congested shared cells")

    higher = "A1" if p1 > p2 else "A2" if p2 > p1 else None
    if higher:
        why.append(
            f"Preserves faster access for the higher-priority emergency "
            f"({higher}: {lab1 if higher == 'A1' else lab2}, priority {max(p1, p2)})"
        )

    starved_selfish = (selfish_overlap > 0) and (sd1 >= _STARVE_S or sd2 >= _STARVE_S)
    if starved_selfish and (d1 < _STARVE_S and d2 < _STARVE_S):
        victim = "Ambulance 2" if sd2 >= sd1 else "Ambulance 1"
        why.append(
            f"Prevents {victim} from being traffic-starved "
            f"(independent pair delayed that unit by {max(sd1, sd2) / 60.0:.1f} min)"
        )
        starvation = "prevented"
    elif overlap > 0 and (d1 >= _STARVE_S or d2 >= _STARVE_S) and max(p1, p2) > min(p1, p2):
        holder = "Ambulance 1" if p1 > p2 else "Ambulance 2"
        why.append(
            f"Clinical urgency overrides fairness: {holder} keeps corridor priority "
            f"(priority {max(p1, p2)} vs {min(p1, p2)})"
        )
        starvation = "accepted"
        conflict = "priority_hold"
    elif overlap <= 0.25:
        starvation = "prevented" if selfish_overlap > 0.5 else "not_applicable"
    else:
        starvation = "not_applicable"

    combined = float(best["eta1_s"]) + float(best["eta2_s"])
    selfish_combined = float(selfish["eta1_s"]) + float(selfish["eta2_s"])
    if combined + 1 < selfish_combined or (overlap < selfish_overlap - 0.01):
        why.append(
            f"Minimizes combined emergency delay "
            f"({round(combined / 60.0, 1)} min vs {round(selfish_combined / 60.0, 1)} min if each took its own fastest path)"
        )

    if runner and runner.get("id") != best.get("id"):
        why.append(
            f"Selected {best['label']} over {runner['label']} "
            f"(combined cost {round(best['cost'], 1)} vs {round(runner['cost'], 1)})"
        )

    if not why:
        why.append("Lowest combined emergency response cost among calculated route pairs")

    if starvation == "prevented":
        strategy = "Lowest overall emergency response cost · traffic starvation prevented"
    elif conflict == "priority_hold":
        strategy = "Clinical-priority corridor hold · fairness deferred"
    elif overlap <= 0:
        strategy = "Independent corridors · lowest combined travel cost"
    else:
        strategy = "Lowest overall emergency response cost"

    return why, starvation, conflict, strategy


def simulate_dual_custom_routes(
    ambulance_1: dict[str, Any],
    pickup_1: tuple[float, float],
    destination_1: tuple[float, float],
    ambulance_2: dict[str, Any],
    pickup_2: tuple[float, float],
    destination_2: tuple[float, float],
    *,
    is_raining: bool = False,
    prefer: str = "fastest",
    traffic_points: list[dict[str, Any]] | None = None,
    previous_drop_sig: str | None = None,
    previous_pickup_sig: str | None = None,
    previous_drop_sig_2: str | None = None,
    previous_pickup_sig_2: str | None = None,
    hospital_1: dict[str, Any] | None = None,
    hospital_2: dict[str, Any] | None = None,
    emergency_category: str | None = None,
    emergency_category_2: str | None = None,
    flags: dict[str, bool] | None = None,
    flags_2: dict[str, bool] | None = None,
    hospital_rerouted: bool = False,
    hospital_rerouted_2: bool = False,
) -> dict[str, Any]:
    """Jointly assign routes for two admin-simulation missions using the live engine.

    Candidates come from ``simulate_custom_route`` / graph alternatives plus one
    occupancy-aware Dijkstra pass each. Combinations are scored together; this
    does not mutate live SOS dispatch.
    """
    from app.services.corridor import overlap_stats, path_cells, priority_label as corridor_priority_label

    points = [p for p in (traffic_points or []) if p]
    sim1 = simulate_custom_route(
        ambulance_1,
        pickup_1,
        destination_1,
        is_raining=is_raining,
        prefer=prefer,
        traffic_points=points or None,
        previous_drop_sig=previous_drop_sig,
        previous_pickup_sig=previous_pickup_sig,
        hospital=hospital_1,
        emergency_category=emergency_category,
        flags=flags,
        hospital_rerouted=hospital_rerouted,
    )
    sim2 = simulate_custom_route(
        ambulance_2,
        pickup_2,
        destination_2,
        is_raining=is_raining,
        prefer=prefer,
        traffic_points=points or None,
        previous_drop_sig=previous_drop_sig_2,
        previous_pickup_sig=previous_pickup_sig_2,
        hospital=hospital_2,
        emergency_category=emergency_category_2,
        flags=flags_2,
        hospital_rerouted=hospital_rerouted_2,
    )

    drops1 = _drop_candidates(sim1)
    drops2 = _drop_candidates(sim2)

    # One extra engine pass each: penalize the other mission's independently chosen path.
    extra1 = optimizer.compute_route(
        pickup_1,
        destination_1,
        emergency=True,
        is_raining=is_raining,
        prefer=prefer,
        enrich=True,
        traffic_points=points or None,
        avoid_paths=[_full_sim_path(sim2)] if _full_sim_path(sim2) else None,
    )
    extra2 = optimizer.compute_route(
        pickup_2,
        destination_2,
        emergency=True,
        is_raining=is_raining,
        prefer=prefer,
        enrich=True,
        traffic_points=points or None,
        avoid_paths=[_full_sim_path(sim1)] if _full_sim_path(sim1) else None,
    )
    drops1 = _append_unique_drop(drops1, _pack_engine_drop(extra1, len(drops1) + 1, "corridor_avoid"))
    drops2 = _append_unique_drop(drops2, _pack_engine_drop(extra2, len(drops2) + 1, "corridor_avoid"))

    pickup1 = [tuple(p) for p in (sim1.get("pickup_route") or []) if p]
    pickup2 = [tuple(p) for p in (sim2.get("pickup_route") or []) if p]
    pickup1_min = float(sim1.get("pickup_minutes") or 0.0)
    pickup2_min = float(sim2.get("pickup_minutes") or 0.0)
    indep1_s = pickup1_min * 60.0 + float(drops1[0]["duration_s"] if drops1 else sim1.get("transport_seconds") or 0)
    indep2_s = pickup2_min * 60.0 + float(drops2[0]["duration_s"] if drops2 else sim2.get("transport_seconds") or 0)
    p1 = int(sim1.get("priority") or _sim_priority(emergency_category, flags))
    p2 = int(sim2.get("priority") or _sim_priority(emergency_category_2, flags_2))
    lab1 = corridor_priority_label(p1)
    lab2 = corridor_priority_label(p2)

    combos: list[dict[str, Any]] = []
    for d1 in drops1:
        for d2 in drops2:
            path1 = pickup1 + list(d1["coords"])
            path2 = pickup2 + list(d2["coords"])
            stats = overlap_stats(path1, path2)
            eta1_s = pickup1_min * 60.0 + float(d1["duration_s"] or 0)
            eta2_s = pickup2_min * 60.0 + float(d2["duration_s"] or 0)
            delay1_s = max(0.0, eta1_s - indep1_s)
            delay2_s = max(0.0, eta2_s - indep2_s)
            cells1, cells2 = path_cells(path1), path_cells(path2)
            shared_cells = cells1 & cells2
            shared_traffic = 0
            if points and shared_cells:
                for pt in points:
                    try:
                        spot = [(float(pt["lat"]), float(pt["lng"]))]
                    except (KeyError, TypeError, ValueError):
                        continue
                    if path_cells(spot) & shared_cells:
                        shared_traffic += 1
            traffic1 = _path_near_traffic(path1, points)
            traffic2 = _path_near_traffic(path2, points)
            cost = _combo_cost(
                eta1_s=eta1_s,
                eta2_s=eta2_s,
                p1=p1,
                p2=p2,
                overlap_delay_s=float(stats.get("delay_seconds") or 0),
                overlap_km=float(stats.get("km") or 0),
                delay1_s=delay1_s,
                delay2_s=delay2_s,
                shared_traffic=shared_traffic,
            )
            label = f"A1 {d1['label']} + A2 {d2['label']}"
            combos.append(
                {
                    "id": f"{d1['id']}+{d2['id']}",
                    "label": label,
                    "a1_route": d1["label"],
                    "a2_route": d2["label"],
                    "a1_kind": d1.get("kind"),
                    "a2_kind": d2.get("kind"),
                    "eta1_minutes": round(eta1_s / 60.0, 1),
                    "eta2_minutes": round(eta2_s / 60.0, 1),
                    "eta1_s": eta1_s,
                    "eta2_s": eta2_s,
                    "overlap_km": float(stats.get("km") or 0),
                    "overlap_delay_s": float(stats.get("delay_seconds") or 0),
                    "overlap_route": stats.get("points") or [],
                    "delay1_s": delay1_s,
                    "delay2_s": delay2_s,
                    "shared_traffic": shared_traffic,
                    "traffic_hits_a1": traffic1,
                    "traffic_hits_a2": traffic2,
                    "cost": cost,
                    "drop1": d1,
                    "drop2": d2,
                }
            )

    if not combos:
        sim1["mission2"] = sim2
        sim1["dual"] = {"active": False, "reason": "No routable combination"}
        return sim1

    ranked = sorted(combos, key=lambda c: (c["cost"], c["eta1_s"] + c["eta2_s"], c["overlap_km"]))
    best = ranked[0]
    selfish = next((c for c in combos if c["id"] == f"{drops1[0]['id']}+{drops2[0]['id']}"), ranked[0])
    runner = ranked[1] if len(ranked) > 1 else None
    why, starvation, conflict, strategy = _dual_why(best, selfish, runner, p1, p2, lab1, lab2)

    chosen1 = _apply_selected_drop(sim1, best["drop1"], pickup_min=pickup1_min)
    chosen2 = _apply_selected_drop(sim2, best["drop2"], pickup_min=pickup2_min)
    chosen1["rerouted"] = bool(sim1.get("rerouted") or best["drop1"]["path_sig"] != (drops1[0].get("path_sig") if drops1 else ""))
    chosen2["rerouted"] = bool(sim2.get("rerouted") or best["drop2"]["path_sig"] != (drops2[0].get("path_sig") if drops2 else ""))
    if previous_drop_sig and previous_drop_sig != chosen1.get("path_sig_drop"):
        chosen1["rerouted"] = True
    if previous_drop_sig_2 and previous_drop_sig_2 != chosen2.get("path_sig_drop"):
        chosen2["rerouted"] = True

    coord_reason = None
    if best["drop1"].get("kind") == "corridor_avoid" or best["drop2"].get("kind") == "corridor_avoid":
        coord_reason = "Route changed because of multi-ambulance corridor coordination (occupied-path penalty in the graph)."
        why = list(why) + [coord_reason]

    a1_eta = chosen1.get("eta_minutes")
    a2_eta = chosen2.get("eta_minutes")
    dual_reason = (
        f"Simulation · combined optimization: Ambulance 1 ({chosen1.get('ambulance_id')}) "
        f"{best['a1_route']} {a1_eta} min; Ambulance 2 ({chosen2.get('ambulance_id')}) "
        f"{best['a2_route']} {a2_eta} min. {strategy}"
    )
    chosen1["reason"] = f"{dual_reason} {chosen1.get('reason') or ''}".strip()
    chosen2["reason"] = f"{dual_reason} {chosen2.get('reason') or ''}".strip()

    affected = []
    if best.get("traffic_hits_a1"):
        affected.append("A1")
    if best.get("traffic_hits_a2"):
        affected.append("A2")

    combinations_view = []
    for row in ranked[:6]:
        combinations_view.append(
            {
                "id": row["id"],
                "label": row["label"],
                "a1_route": row["a1_route"],
                "a2_route": row["a2_route"],
                "eta1_minutes": row["eta1_minutes"],
                "eta2_minutes": row["eta2_minutes"],
                "overlap_km": row["overlap_km"],
                "overlap_delay_s": row["overlap_delay_s"],
                "cost": round(row["cost"], 1),
                "selected": row["id"] == best["id"],
                "lost_reason": (
                    None
                    if row["id"] == best["id"]
                    else (
                        f"Higher combined cost ({round(row['cost'], 1)} vs {round(best['cost'], 1)})"
                        + (
                            f"; {row['overlap_km']:.2f} km shared corridor"
                            if row["overlap_km"] > best["overlap_km"]
                            else ""
                        )
                    )
                ),
            }
        )

    decision = {
        "title": "MULTI-AMBULANCE ROUTE DECISION",
        "selected_route": best["label"],
        "algorithm": chosen1.get("algorithm") or sim1.get("algorithm"),
        "eta_minutes": round((float(best["eta1_s"]) + float(best["eta2_s"])) / 60.0, 1),
        "distance_km": round(
            float(chosen1.get("total_distance_km") or 0) + float(chosen2.get("total_distance_km") or 0), 2
        ),
        "traffic": _traffic_summary(points, int(best.get("traffic_hits_a1") or 0) + int(best.get("traffic_hits_a2") or 0), chosen1.get("rerouted") or chosen2.get("rerouted")),
        "road_conditions": strategy,
        "a1": {
            "ambulance_id": chosen1.get("ambulance_id"),
            "route": best["a1_route"],
            "eta_minutes": a1_eta,
            "priority": p1,
            "priority_label": lab1,
        },
        "a2": {
            "ambulance_id": chosen2.get("ambulance_id"),
            "route": best["a2_route"],
            "eta_minutes": a2_eta,
            "priority": p2,
            "priority_label": lab2,
        },
        "why": why,
        "traffic_starvation": starvation,
        "corridor_conflict": conflict,
        "combined_strategy": strategy,
        "selected_combination": best["label"],
        "runner_up": (runner or {}).get("label"),
        "conditions_met": why,
        "decision": dual_reason,
        "coordination_note": coord_reason,
    }
    chosen1["decision"] = decision

    dual = {
        "active": True,
        "label": "Simulation · combined optimization",
        "a1_eta_minutes": a1_eta,
        "a2_eta_minutes": a2_eta,
        "combined_eta_minutes": round((float(best["eta1_s"]) + float(best["eta2_s"])) / 60.0, 1),
        "traffic_starvation": starvation,
        "corridor_conflict": conflict,
        "combined_strategy": strategy,
        "selected_combination": best["label"],
        "combinations": combinations_view,
        "why": why,
        "overlap_km": best["overlap_km"],
        "overlap_route": best.get("overlap_route") or [],
        "affected_by_traffic": affected,
        "rerouted": bool(chosen1.get("rerouted") or chosen2.get("rerouted")),
        "coordination_note": coord_reason,
        "priority_a1": p1,
        "priority_a2": p2,
        "independent_combination": selfish["label"],
        "independent_etas": {
            "a1_minutes": round(indep1_s / 60.0, 1),
            "a2_minutes": round(indep2_s / 60.0, 1),
        },
    }
    chosen1["mission2"] = chosen2
    chosen1["dual"] = dual
    chosen1["candidate_routes"] = sim1.get("candidate_routes") or []
    return chosen1


def maybe_emergency_hospital_reroute(
    mission: dict[str, Any],
    score: int,
    *,
    origin: tuple[float, float] | None = None,
    hospitals: list[dict[str, Any]] | None = None,
    ambulance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """If danger rating is 8–10, switch destination to nearest eligible hospital when it differs."""
    from app.services.fleet import get_ambulance, get_hospitals, update_ambulance_paths
    from app.services.graph_router import path_signature

    n = max(1, min(10, int(score)))
    if n < 8:
        return mission

    hospitals = hospitals if hospitals is not None else get_hospitals()
    if not mission.get("simulation"):
        hospitals = [h for h in hospitals if not h.get("simulation")]

    amb = ambulance or get_ambulance(mission.get("ambulance_id")) or mission.get("ambulance") or {}
    if origin is None:
        origin = (float(amb.get("lat") or 0), float(amb.get("lng") or 0))
    if not origin[0] and not origin[1]:
        pickup = mission.get("pickup") or {}
        origin = (float(pickup.get("lat") or 0), float(pickup.get("lng") or 0))

    requirement = dispatch_requirement(
        mission.get("emergency_category"),
        mission.get("flags") or {},
        mission.get("age_group"),
        bool(mission.get("accessibility_need")),
    )
    chosen = nearest_eligible_hospital(
        origin,
        hospitals,
        requirement,
        is_raining=bool(mission.get("is_raining")),
        traffic_points=mission.get("sim_traffic") or mission.get("traffic_points"),
    )
    if not chosen:
        return mission

    new_hosp = chosen["hospital"]
    prev = mission.get("hospital") or {}
    prev_id = mission.get("hospital_id") or prev.get("id")
    new_id = new_hosp.get("id")
    notice = {
        "danger_rating": n,
        "previous_hospital": prev.get("name") or mission.get("hospital_name"),
        "previous_hospital_id": prev_id,
        "new_hospital": new_hosp.get("name"),
        "new_hospital_id": new_id,
        "match_status": chosen.get("match_status"),
        "reason": "Critical deterioration — nearest eligible hospital selected.",
        "changed": prev_id != new_id,
    }
    if prev_id == new_id:
        notice["reason"] = "Assigned hospital is still the nearest eligible facility."
        mission["emergency_reroute"] = notice
        return mission

    pickup = mission.get("pickup") or {}
    pickup_pt = (float(pickup.get("lat") or origin[0]), float(pickup.get("lng") or origin[1]))
    dest = (float(new_hosp["lat"]), float(new_hosp["lng"]))
    phase = mission.get("phase") or "pickup"
    route_origin = origin if phase == "drop" else pickup_pt
    drop_res = optimizer.compute_route(
        route_origin,
        dest,
        emergency=True,
        is_raining=bool(mission.get("is_raining")),
        prefer="fastest",
        enrich=True,
        traffic_points=mission.get("traffic_points") or None,
    )
    drop_coords = drop_res.get("coords") or chosen.get("route") or []
    drop_sec = float(drop_res.get("duration") or chosen.get("transport_seconds") or 0)
    pickup_coords = mission.get("pickup_route") or []
    pickup_sec = float(mission.get("pickup_seconds") or 0)
    if phase == "drop":
        pickup_coords = []
        pickup_sec = 0.0
        total_sec = drop_sec
    else:
        total_sec = pickup_sec + drop_sec

    mission["hospital"] = new_hosp
    mission["hospital_id"] = new_id
    mission["hospital_name"] = new_hosp.get("name")
    mission["route"] = drop_coords
    mission["drop_route"] = drop_coords
    mission["transport_seconds"] = int(round(drop_sec))
    mission["transport_minutes"] = round(drop_sec / 60.0, 1)
    mission["eta_seconds"] = int(round(total_sec))
    mission["eta_minutes"] = round(total_sec / 60.0, 1)
    mission["transport_distance_km"] = _path_km(drop_coords)
    mission["path_sig_drop"] = drop_res.get("path_sig") or path_signature(drop_coords)
    mission["candidate_routes"] = drop_res.get("alternatives") or []
    mission["emergency_reroute"] = notice
    mission["hospital_rerouted"] = True
    reason = (
        f"EMERGENCY REROUTE · Danger Rating {n}/10. "
        f"Previous Hospital: {notice['previous_hospital']}. "
        f"New Hospital: {notice['new_hospital']}. "
        f"{notice['reason']}"
    )
    mission["reason"] = reason
    constraints = dict(mission.get("constraints") or {})
    constraints["hospital_match_status"] = chosen.get("match_status")
    constraints["road_conditions"] = reason
    mission["constraints"] = constraints
    decision = dict(mission.get("decision") or {})
    decision.update(
        {
            "selected_route": "Route 1",
            "eta_minutes": mission["eta_minutes"],
            "distance_km": mission.get("transport_distance_km"),
            "decision": reason,
            "conditions_met": [
                f"Danger rating {n}/10 (critical)",
                "Nearest eligible hospital by routed travel time",
                f"Match: {str(chosen.get('match_status') or '').replace('_', ' ')}",
            ],
        }
    )
    mission["decision"] = decision
    try:
        update_ambulance_paths(
            mission.get("ambulance_id"),
            pickup_path=pickup_coords if phase != "drop" else None,
            drop_path=drop_coords,
            keep_position=True,
        )
    except Exception:
        pass
    return mission
