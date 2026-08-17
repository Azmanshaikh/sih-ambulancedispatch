"""NetworkX road-graph routing built from live TomTom / OSRM corridors.

Instead of the old hand-rolled A* on a 4-node mock graph, this module:

1. Pulls several *real-road* alternatives for an origin -> destination pair
   (TomTom `calculateRoute` with alternatives + live traffic, OSRM as fallback).
2. Fuses those polylines into a single ``networkx.DiGraph`` where nodes are
   ~40 m road cells and edges carry both ``length_m`` (for the shortest route)
   and ``time_s`` (live-traffic travel time, for the fastest route). Reverse
   edges are added so an emergency unit may legally contra-flow a one-way.
3. Runs Dijkstra (``networkx.shortest_path``) twice — once weighted by distance,
   once by time — so we get the genuine shortest *and* fastest paths and can
   compare them.
4. Adds a congestion penalty to any edge whose cell is already occupied by
   another active ambulance corridor (``avoid_paths``), so a lower-priority
   unit is naturally routed around a busy corridor rather than stacking onto it.

The module degrades gracefully: if networkx is missing or no candidates can be
fetched, callers fall back to the direct TomTom/OSRM routing in
``dispatch_optimizer``.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

import requests

try:  # networkx is optional at import time; callers fall back if unavailable.
    import networkx as nx

    _NX_OK = True
except Exception:  # pragma: no cover - only hit when dependency missing
    nx = None  # type: ignore
    _NX_OK = False

NODE_M = 40.0  # graph node quantization (metres)
OCC_PENALTY = 4.0  # time multiplier for edges on an occupied corridor
_DEG = NODE_M / 111_000.0

_CACHE_TTL_S = 20.0
_cache: dict[tuple, tuple[float, list[dict[str, Any]]]] = {}
_cache_lock = threading.Lock()


def available() -> bool:
    return _NX_OK


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, h)))


def _node_key(lat: float, lng: float) -> tuple[int, int]:
    return (round(lat / _DEG), round(lng / _DEG))


def _seg_lengths(coords: list[tuple[float, float]]) -> tuple[list[float], float]:
    segs = [_haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    return segs, (sum(segs) or 1.0)


def _tomtom_alternatives(
    origin: tuple[float, float],
    dest: tuple[float, float],
    key: str,
    route_type: str,
    traffic: bool,
) -> list[dict[str, Any]]:
    url = (
        "https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}/json"
        f"?key={key}&travelMode=car&routeType={route_type}"
        f"&traffic={'true' if traffic else 'false'}&maxAlternatives=2"
    )
    out: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        for route in data.get("routes") or []:
            summary = route.get("summary") or {}
            pts = (route.get("legs") or [{}])[0].get("points") or []
            coords = [(p["latitude"], p["longitude"]) for p in pts]
            if len(coords) < 2:
                continue
            out.append(
                {
                    "coords": coords,
                    "duration": float(summary.get("travelTimeInSeconds") or 0.0),
                    "distance": float(summary.get("lengthInMeters") or 0.0),
                }
            )
    except Exception as exc:  # pragma: no cover - network failure path
        print("graph_router TomTom error:", exc)
    return out


def _osrm_alternatives(origin: tuple[float, float], dest: tuple[float, float]) -> list[dict[str, Any]]:
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        "?overview=full&geometries=geojson&alternatives=true"
    )
    out: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "JEEVAN-dispatch/1.0"})
        data = resp.json()
        if data.get("code") == "Ok":
            for route in data.get("routes") or []:
                coords = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
                if len(coords) < 2:
                    continue
                out.append(
                    {
                        "coords": coords,
                        "duration": float(route.get("duration") or 0.0),
                        "distance": float(route.get("distance") or 0.0),
                    }
                )
    except Exception as exc:  # pragma: no cover - network failure path
        print("graph_router OSRM error:", exc)
    return out


def _fetch_candidates(
    origin: tuple[float, float],
    dest: tuple[float, float],
    key: str | None,
    enrich: bool,
) -> tuple[list[dict[str, Any]], str]:
    ckey = (
        round(origin[0], 4),
        round(origin[1], 4),
        round(dest[0], 4),
        round(dest[1], 4),
        bool(enrich),
        bool(key),
    )
    now = time.time()
    with _cache_lock:
        hit = _cache.get(ckey)
        if hit and now - hit[0] < _CACHE_TTL_S:
            cands, provider = hit[1]
            return list(cands), provider

    candidates: list[dict[str, Any]] = []
    provider = "osrm"
    if key:
        candidates = _tomtom_alternatives(origin, dest, key, "fastest", traffic=True)
        if enrich:
            candidates += _tomtom_alternatives(origin, dest, key, "shortest", traffic=False)
        if candidates:
            provider = "tomtom"
    if not candidates:
        candidates = _osrm_alternatives(origin, dest)
        provider = "osrm"

    with _cache_lock:
        _cache[ckey] = (now, (list(candidates), provider))
    return candidates, provider


def _build_graph(candidates: list[dict[str, Any]]):
    graph = nx.DiGraph()
    for cand in candidates:
        coords = cand["coords"]
        segs, total = _seg_lengths(coords)
        duration = float(cand.get("duration") or 0.0)
        for i in range(len(coords) - 1):
            a, b = coords[i], coords[i + 1]
            ka, kb = _node_key(*a), _node_key(*b)
            if ka == kb:
                continue
            seg_len = segs[i] or _haversine_m(a, b)
            seg_time = duration * (seg_len / total) if duration else seg_len / 13.9
            if ka not in graph:
                graph.add_node(ka, coord=a)
            if kb not in graph:
                graph.add_node(kb, coord=b)
            for u, v in ((ka, kb), (kb, ka)):  # reverse edge = emergency contra-flow
                if graph.has_edge(u, v):
                    e = graph[u][v]
                    e["length_m"] = min(e["length_m"], seg_len)
                    e["time_s"] = min(e["time_s"], seg_time)
                else:
                    graph.add_edge(u, v, length_m=seg_len, time_s=seg_time)
    return graph


def _nearest_node(graph, point: tuple[float, float]):
    best = None
    best_d = float("inf")
    for node, coord in graph.nodes(data="coord"):
        d = _haversine_m(point, coord)
        if d < best_d:
            best_d = d
            best = node
    return best


def _occupied_keys(avoid_paths: list[list[tuple[float, float]]] | None) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for path in avoid_paths or []:
        pts = [p for p in path if p]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            dist = _haversine_m(a, b)
            steps = max(1, int(dist / NODE_M))
            for s in range(steps + 1):
                t = s / steps
                keys.add(_node_key(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        if len(pts) == 1:
            keys.add(_node_key(*pts[0]))
    return keys


def _path_metrics(graph, nodes: list) -> tuple[list[tuple[float, float]], float, float]:
    coords = [graph.nodes[n]["coord"] for n in nodes]
    length_m = 0.0
    time_s = 0.0
    for u, v in zip(nodes, nodes[1:]):
        e = graph[u][v]
        length_m += e["length_m"]
        time_s += e["time_s"]
    return coords, length_m, time_s


def route(
    origin: tuple[float, float],
    dest: tuple[float, float],
    *,
    api_key: str | None = None,
    avoid_paths: list[list[tuple[float, float]]] | None = None,
    prefer: str = "fastest",
    enrich: bool = False,
) -> dict[str, Any] | None:
    """Return a NetworkX Dijkstra route or ``None`` (so the caller falls back).

    Result keys: ``coords``, ``duration`` (s, raw traffic time), ``distance`` (m),
    ``source``, ``shortest_km``, ``fastest_min``, ``occupied_hits``, ``nodes``.
    """
    if not _NX_OK:
        return None
    candidates, provider = _fetch_candidates(origin, dest, api_key, enrich)
    if not candidates:
        return None

    graph = _build_graph(candidates)
    if graph.number_of_nodes() < 2:
        return None

    src = _nearest_node(graph, origin)
    dst = _nearest_node(graph, dest)
    if src is None or dst is None or src == dst:
        return None

    occupied = _occupied_keys(avoid_paths)

    def time_weight(u, v, data) -> float:
        t = data.get("time_s", data.get("length_m", 1.0) / 13.9)
        if u in occupied or v in occupied:
            t *= OCC_PENALTY
        return t

    try:
        fastest_nodes = nx.shortest_path(graph, src, dst, weight=time_weight)
    except Exception:
        fastest_nodes = None
    try:
        shortest_nodes = nx.shortest_path(graph, src, dst, weight="length_m")
    except Exception:
        shortest_nodes = None

    if not fastest_nodes and not shortest_nodes:
        return None
    fastest_nodes = fastest_nodes or shortest_nodes
    shortest_nodes = shortest_nodes or fastest_nodes

    f_coords, f_len, f_time = _path_metrics(graph, fastest_nodes)
    s_coords, s_len, s_time = _path_metrics(graph, shortest_nodes)

    if prefer == "shortest":
        chosen_nodes, coords, dist_m, dur_s = shortest_nodes, s_coords, s_len, s_time
    else:
        chosen_nodes, coords, dist_m, dur_s = fastest_nodes, f_coords, f_len, f_time

    # Snap true endpoints so the drawn line starts/ends exactly on incident/hospital.
    if coords and _haversine_m(coords[0], origin) > 5:
        coords = [origin] + coords
    if coords and _haversine_m(coords[-1], dest) > 5:
        coords = coords + [dest]

    occupied_hits = sum(1 for n in chosen_nodes if n in occupied)
    return {
        "coords": coords,
        "duration": dur_s,
        "distance": dist_m,
        "source": f"networkx+{provider}",
        "shortest_km": round(s_len / 1000.0, 2),
        "fastest_min": round(f_time / 60.0, 1),
        "occupied_hits": occupied_hits,
        "nodes": len(chosen_nodes),
        "graph_nodes": graph.number_of_nodes(),
    }
