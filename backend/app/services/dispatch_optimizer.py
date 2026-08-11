import os
import requests
from typing import List, Dict, Tuple
from app.services.routing import a_star_search

class DispatchOptimizer:
    def __init__(self):
        # Mock graph and coordinates for fallback demonstration of A* based routing
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
        """Helper to snap a lat/lng location to the nearest node in the mock graph."""
        import math
        nearest_node = None
        min_dist = float('inf')
        for node, coord in self.mock_coords.items():
            dist = math.sqrt((location[0] - coord[0])**2 + (location[1] - coord[1])**2)
            if dist < min_dist:
                min_dist = dist
                nearest_node = node
        return nearest_node or "node_a"

    def get_tomtom_route(self, origin: tuple, destination: tuple, api_key: str) -> Tuple[float, List[Tuple[float, float]]]:
        """Calls the TomTom API to get live-traffic driving time and route geometry."""
        # TomTom expects latitude,longitude:latitude,longitude
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin[0]},{origin[1]}:{destination[0]},{destination[1]}/json?key={api_key}&traffic=true"
        try:
            response = requests.get(url)
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                route = data["routes"][0]
                duration = route["summary"]["travelTimeInSeconds"]
                
                # Extract points directly from legs (no polyline decoding needed for TomTom!)
                points = route["legs"][0]["points"]
                route_coords = [(pt["latitude"], pt["longitude"]) for pt in points]
                
                return duration, route_coords
            print("TomTom API Error:", data)
        except Exception as e:
            print("Failed to contact TomTom API:", e)
        return float('inf'), []

    def optimize_dispatch(self, incident_location: tuple, ambulances: List[Dict]) -> dict:
        """
        Uses TomTom API to find the fastest ambulance route based on live traffic.
        Falls back to our custom A* algorithm if the API fails.
        Returns a dictionary with 'ambulance_id' and 'route'.
        """
        from app.core.config import settings
        if not ambulances:
            return {"ambulance_id": None, "route": []}
            
        api_key = settings.TOMTOM_API_KEY if hasattr(settings, "TOMTOM_API_KEY") else os.environ.get("TOMTOM_API_KEY")
        
        best_ambulance_id = None
        best_time = float('inf')
        best_route = []
        
        if api_key:
            # --- REAL ROAD NETWORK (TomTom Live Traffic API) ---
            print("Attempting TomTom API for live traffic routing...")
            for amb in ambulances:
                amb_loc = amb.get("location", (0, 0)) 
                travel_time, route_coords = self.get_tomtom_route(amb_loc, incident_location, api_key)
                
                if travel_time < best_time:
                    best_time = travel_time
                    best_ambulance_id = amb.get("id")
                    best_route = route_coords
        else:
            print("WARNING: TOMTOM_API_KEY missing from .env, skipping live traffic routing.")
                
        # --- FALLBACK MOCK GRAPH (A* Algorithm) ---
        if best_time == float('inf'):
            print("Falling back to custom A* algorithm...")
            incident_node = self._find_nearest_node(incident_location)
            for amb in ambulances:
                amb_loc = amb.get("location", (0, 0)) 
                amb_node = self._find_nearest_node(amb_loc)
                
                path, cost = a_star_search(
                    start=amb_node, 
                    goal=incident_node, 
                    graph=self.mock_graph, 
                    node_coordinates=self.mock_coords
                )
                
                if cost < best_time:
                    best_time = cost
                    best_ambulance_id = amb.get("id")
                    best_route = [self.mock_coords[node] for node in path]
                
        # Final fallback if routing fails completely
        if not best_ambulance_id:
            best_ambulance_id = ambulances[0].get("id")
            
        return {
            "ambulance_id": best_ambulance_id,
            "route": best_route,
            "eta_seconds": best_time if best_time != float('inf') else 0
        }

optimizer = DispatchOptimizer()

def get_optimal_ambulance(incident_lat: float, incident_lng: float, available_ambulances: list) -> dict:
    return optimizer.optimize_dispatch((incident_lat, incident_lng), available_ambulances)
