import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests

from app.services.routing import a_star_search


class DispatchOptimizer:
    def __init__(self):
        self._tomtom_available: bool | None = None
        self.mock_graph = {
            "node_a": {"node_b": 5.0, "node_c": 10.0},
            "node_b": {"node_a": 5.0, "node_d": 8.0, "node_c": 2.0},
            "node_c": {"node_a": 10.0, "node_b": 2.0, "node_d": 4.0},
            "node_d": {"node_b": 8.0, "node_c": 4.0},
        }
        self.mock_coords = {
            "node_a": (0.0, 0.0),
            "node_b": (3.0, 4.0),
            "node_c": (6.0, 0.0),
            "node_d": (6.0, 8.0),
        }

    def _find_nearest_node(self, location: tuple) -> str:
        import math

        nearest_node = None
        min_dist = float("inf")
        for node, coord in self.mock_coords.items():
            dist = math.sqrt((location[0] - coord[0]) ** 2 + (location[1] - coord[1]) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest_node = node
        return nearest_node or "node_a"

    def get_tomtom_route(
        self, origin: tuple, destination: tuple, api_key: str
    ) -> Tuple[float, List[Tuple[float, float]]]:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute/"
            f"{origin[0]},{origin[1]}:{destination[0]},{destination[1]}/json"
            f"?key={api_key}&traffic=true&travelMode=car&routeType=fastest"
        )
        try:
            response = requests.get(url, timeout=8)
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                route = data["routes"][0]
                duration = route["summary"]["travelTimeInSeconds"]
                points = route["legs"][0]["points"]
                route_coords = [(pt["latitude"], pt["longitude"]) for pt in points]
                return duration, route_coords
            print("TomTom API Error:", data.get("error", data.get("detailedError", "unknown")))
        except Exception as e:
            print("Failed to contact TomTom API:", e)
        return float("inf"), []

    def get_osrm_route(
        self, origin: tuple, destination: tuple
    ) -> Tuple[float, List[Tuple[float, float]]]:
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            "?overview=full&geometries=geojson"
        )
        try:
            response = requests.get(url, timeout=8, headers={"User-Agent": "JEEVAN-dispatch/1.0"})
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                duration = float(route["duration"])
                coords = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
                return duration, coords
        except Exception as e:
            print("Failed to contact OSRM:", e)
        return float("inf"), []

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

    def _route(self, origin: tuple, destination: tuple, api_key: str | None = None):
        """Automatically uses TomTom live traffic when available, otherwise OSRM roads."""
        key = (api_key or "").strip() or self._tomtom_key()
        if key and self._detect_tomtom():
            duration, coords = self.get_tomtom_route(origin, destination, key)
            if duration != float("inf") and coords:
                return duration, coords, "tomtom-live-traffic"
            self._tomtom_available = False

        duration, coords = self.get_osrm_route(origin, destination)
        if duration != float("inf") and coords:
            return duration, coords, "osrm-road-network"
        return float("inf"), [], "none"

    def optimize_dispatch(self, incident_location: tuple, ambulances: List[Dict]) -> dict:
        if not ambulances:
            return {"ambulance_id": None, "route": []}

        best_ambulance_id = None
        best_time = float("inf")
        best_route: List[Tuple[float, float]] = []

        for amb in ambulances:
            amb_loc = amb.get("location", (0, 0))
            travel_time, route_coords, _source = self._route(amb_loc, incident_location)
            if travel_time < best_time:
                best_time = travel_time
                best_ambulance_id = amb.get("id")
                best_route = route_coords

        if best_time == float("inf"):
            incident_node = self._find_nearest_node(incident_location)
            for amb in ambulances:
                amb_loc = amb.get("location", (0, 0))
                amb_node = self._find_nearest_node(amb_loc)
                path, cost = a_star_search(
                    start=amb_node,
                    goal=incident_node,
                    graph=self.mock_graph,
                    node_coordinates=self.mock_coords,
                )
                if cost < best_time:
                    best_time = cost
                    best_ambulance_id = amb.get("id")
                    best_route = [self.mock_coords[node] for node in path]

        if not best_ambulance_id:
            best_ambulance_id = ambulances[0].get("id")

        return {
            "ambulance_id": best_ambulance_id,
            "route": best_route,
            "eta_seconds": best_time if best_time != float("inf") else 0,
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

    def _pick_ambulance(self, incident_location: tuple, ambulances: List[Dict[str, Any]]) -> dict[str, Any] | None:
        available = [a for a in ambulances if a.get("status") in (None, "available")]
        pool = available or [a for a in ambulances if a.get("status") != "busy"] or ambulances
        if not pool:
            return None
        ranked = sorted(
            pool,
            key=lambda a: self._haversine_km((a["lat"], a["lng"]), incident_location),
        )[:5]
        best_unit = None
        best_time = float("inf")
        best_route: List[Tuple[float, float]] = []
        for amb in ranked:
            duration, coords, _source = self._route((amb["lat"], amb["lng"]), incident_location)
            if duration < best_time:
                best_time = duration
                best_unit = amb
                best_route = coords
        if best_unit is None:
            best_unit = ranked[0]
            best_time = 0
        return {
            "ambulance": best_unit,
            "pickup_seconds": best_time if best_time != float("inf") else 0,
            "pickup_route": best_route,
        }

    def optimize_hospital_dispatch(
        self,
        incident_location: tuple,
        hospitals: List[Dict[str, Any]],
        ambulances: List[Dict[str, Any]],
        is_raining: bool = False,
    ) -> dict:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        peak = self._peak_traffic_factor()
        self._detect_tomtom()
        pickup = self._pick_ambulance(incident_location, ambulances)

        def score_hospital(hosp: Dict[str, Any]) -> dict[str, Any] | None:
            dest = (float(hosp["lat"]), float(hosp["lng"]))
            duration, coords, source = self._route(incident_location, dest)
            if duration == float("inf") or not coords:
                return None
            extra_traffic = 1.0 if source == "tomtom-live-traffic" else peak
            transport = duration * extra_traffic
            pickup_s = float(pickup["pickup_seconds"]) if pickup else 0.0
            effective = pickup_s + transport
            return {
                "hospital": hosp,
                "route": coords,
                "raw_seconds": duration,
                "transport_seconds": transport,
                "pickup_seconds": pickup_s,
                "eta_seconds": effective,
                "source": source,
            }

        scored: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(score_hospital, hosp) for hosp in hospitals]
            for fut in as_completed(futures):
                row = fut.result()
                if row:
                    scored.append(row)

        best: dict[str, Any] | None = min(scored, key=lambda r: r["eta_seconds"]) if scored else None

        if best is None:
            nearest = min(
                hospitals,
                key=lambda h: (h["lat"] - incident_location[0]) ** 2 + (h["lng"] - incident_location[1]) ** 2,
            )
            best = {
                "hospital": nearest,
                "route": [incident_location, (nearest["lat"], nearest["lng"])],
                "raw_seconds": 720,
                "transport_seconds": 720,
                "pickup_seconds": float(pickup["pickup_seconds"]) if pickup else 0.0,
                "eta_seconds": 720,
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
        reason = (
            f"{hospital.get('name')} is the fastest destination "
            f"({pickup_min} min pickup + {transport_min} min to hospital) "
            f"using live traffic routing. Auto-assigned — no staff hospital pick."
            + (f" Specialties: {specs}." if specs else "")
        )
        return {
            "ambulance_id": assigned["id"] if assigned else None,
            "ambulance": assigned,
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
                "routing": best["source"],
                "traffic": "live" if best["source"] == "tomtom-live-traffic" else "estimated-peak",
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


def get_optimal_ambulance(incident_lat: float, incident_lng: float, available_ambulances: list) -> dict:
    return optimizer.optimize_dispatch((incident_lat, incident_lng), available_ambulances)


def get_optimal_hospital_dispatch(
    incident_lat: float,
    incident_lng: float,
    hospitals: list,
    ambulances: list,
    is_raining: bool = False,
) -> dict:
    return optimizer.optimize_hospital_dispatch(
        (incident_lat, incident_lng), hospitals, ambulances, is_raining
    )
