from __future__ import annotations

from app.services.dispatch_optimizer import simulate_dual_custom_routes


SHARED = [(13.1200, 77.5800), (13.1100, 77.5800), (13.1000, 77.5800)]
SPLIT_A = [(13.1200, 77.5720), (13.1100, 77.5720), (13.1000, 77.5800)]
SPLIT_B = [(13.1200, 77.5880), (13.1100, 77.5880), (13.1000, 77.5800)]
PICKUP_A = [(13.1344, 77.5693), (13.1200, 77.5800)]
PICKUP_B = [(13.0995, 77.5963), (13.1200, 77.5800)]


def _alt(rank: int, coords, minutes: float, kind: str = "provider"):
    return {
        "rank": rank,
        "label": f"Route {rank}",
        "kind": "selected" if rank == 1 else kind,
        "coords": coords,
        "duration": minutes * 60.0,
        "eta_minutes": minutes,
        "distance": 2200.0,
        "path_sig": f"{kind}-{rank}-{coords[0][1]:.3f}",
    }


def _sim(amb_id: str, pickup, alts, *, priority: int = 1, pickup_min: float = 2.0, category: str = "general_medical"):
    drop = alts[0]
    return {
        "simulation": True,
        "ambulance_id": amb_id,
        "ambulance": {"id": amb_id, "label": amb_id, "lat": pickup[0][0], "lng": pickup[0][1]},
        "pickup_route": pickup,
        "route": drop["coords"],
        "candidate_routes": alts,
        "pickup_minutes": pickup_min,
        "pickup_seconds": int(pickup_min * 60),
        "transport_minutes": drop["eta_minutes"],
        "transport_seconds": int(drop["duration"]),
        "eta_minutes": pickup_min + drop["eta_minutes"],
        "pickup_distance_km": 1.6,
        "transport_distance_km": 2.2,
        "total_distance_km": 3.8,
        "priority": priority,
        "priority_label": "cardiac" if priority >= 5 else "standard",
        "path_sig_drop": drop["path_sig"],
        "path_sig_pickup": "pickup",
        "algorithm": "mock",
        "decision": {"selected_route": drop["label"], "eta_minutes": pickup_min + drop["eta_minutes"]},
        "emergency_category": category,
        "reason": "independent fastest",
    }


def _fake_compute(origin, dest, **kwargs):
    # Same signature as Route 1 so the extra occupancy pass is de-duplicated in unit tests.
    return {
        "coords": SHARED,
        "duration": 8 * 60.0,
        "distance": 2200.0,
        "path_sig": "selected-1-77.580",
        "traffic_hits": 0,
        "occupied_hits": 1 if kwargs.get("avoid_paths") else 0,
        "engine": "networkx",
        "source": "mock",
        "alternatives": [],
    }


def test_dual_prefers_split_corridors_over_shared(monkeypatch):
    from app.services import dispatch_optimizer

    sim_a = _sim("AMB-101", PICKUP_A, [_alt(1, SHARED, 7), _alt(2, SPLIT_A, 8)])
    sim_b = _sim("AMB-102", PICKUP_B, [_alt(1, SHARED, 8), _alt(2, SPLIT_B, 9)])
    calls = {"n": 0}

    def fake_single(*_args, **_kwargs):
        calls["n"] += 1
        return dict(sim_a) if calls["n"] == 1 else dict(sim_b)

    monkeypatch.setattr(dispatch_optimizer, "simulate_custom_route", fake_single)
    monkeypatch.setattr(dispatch_optimizer.optimizer, "compute_route", _fake_compute)

    out = simulate_dual_custom_routes(
        {"id": "AMB-101", "lat": 13.1344, "lng": 77.5693},
        PICKUP_A[0],
        SHARED[-1],
        {"id": "AMB-102", "lat": 13.0995, "lng": 77.5963},
        PICKUP_B[0],
        SHARED[-1],
    )
    dual = out["dual"]
    assert dual["active"] is True
    selfish = next(c for c in dual["combinations"] if c["label"] == dual["independent_combination"])
    selected = next(c for c in dual["combinations"] if c["selected"])
    assert selected["overlap_km"] < selfish["overlap_km"]
    assert dual["traffic_starvation"] == "prevented"
    assert dual["corridor_conflict"] == "avoided"
    assert any("starved" in w.lower() or "competing" in w.lower() for w in dual["why"])


def test_dual_clinical_urgency_keeps_priority_corridor(monkeypatch):
    from app.services import dispatch_optimizer

    # Splitting costs the cardiac unit 6 extra minutes — urgency should keep the shared corridor.
    sim_a = _sim(
        "AMB-101",
        PICKUP_A,
        [_alt(1, SHARED, 8), _alt(2, SPLIT_A, 14)],
        priority=5,
        category="cardiac",
    )
    sim_b = _sim("AMB-102", PICKUP_B, [_alt(1, SHARED, 9), _alt(2, SPLIT_B, 10)], priority=1)
    calls = {"n": 0}

    def fake_single(*_args, **_kwargs):
        calls["n"] += 1
        return dict(sim_a) if calls["n"] == 1 else dict(sim_b)

    monkeypatch.setattr(dispatch_optimizer, "simulate_custom_route", fake_single)
    monkeypatch.setattr(dispatch_optimizer.optimizer, "compute_route", _fake_compute)

    out = simulate_dual_custom_routes(
        {"id": "AMB-101", "lat": 13.1344, "lng": 77.5693},
        PICKUP_A[0],
        SHARED[-1],
        {"id": "AMB-102", "lat": 13.0995, "lng": 77.5963},
        PICKUP_B[0],
        SHARED[-1],
        emergency_category="cardiac",
        emergency_category_2="general_medical",
        flags={"cardiac": True},
        flags_2={},
    )
    dual = out["dual"]
    assert dual["priority_a1"] == 5
    assert out["eta_minutes"] <= 10.1
    assert "Route 1" in str(dual["selected_combination"])
    assert dual["independent_etas"]["a1_minutes"] <= out["eta_minutes"] + 0.2


def test_dual_traffic_on_shared_corridor_can_flip_assignment(monkeypatch):
    from app.services import dispatch_optimizer

    sim_a = _sim("AMB-101", PICKUP_A, [_alt(1, SHARED, 7.2), _alt(2, SPLIT_A, 7.6)])
    sim_b = _sim("AMB-102", PICKUP_B, [_alt(1, SHARED, 7.3), _alt(2, SPLIT_B, 7.7)])
    calls = {"n": 0}

    def fake_single(*_args, **_kwargs):
        calls["n"] += 1
        return dict(sim_a) if calls["n"] == 1 else dict(sim_b)

    monkeypatch.setattr(dispatch_optimizer, "simulate_custom_route", fake_single)
    monkeypatch.setattr(dispatch_optimizer.optimizer, "compute_route", _fake_compute)

    traffic = [{"lat": 13.1100, "lng": 77.5800, "taps": 4}]
    out = simulate_dual_custom_routes(
        {"id": "AMB-101", "lat": 13.1344, "lng": 77.5693},
        PICKUP_A[0],
        SHARED[-1],
        {"id": "AMB-102", "lat": 13.0995, "lng": 77.5963},
        PICKUP_B[0],
        SHARED[-1],
        traffic_points=traffic,
    )
    dual = out["dual"]
    assert dual["active"] is True
    selected = next(c for c in dual["combinations"] if c["selected"])
    selfish = next(c for c in dual["combinations"] if c["label"] == dual["independent_combination"])
    assert selected["overlap_km"] < selfish["overlap_km"]
    assert dual["corridor_conflict"] == "avoided"
