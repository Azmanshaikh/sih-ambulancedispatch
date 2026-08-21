from __future__ import annotations

from app.services.dispatch_optimizer import (
    dispatch_requirement,
    filter_eligible_hospitals,
    maybe_emergency_hospital_reroute,
    nearest_eligible_hospital,
)
from app.services.fleet import get_hospitals, init_fleet


def setup_function():
    init_fleet()


def test_ten_simulation_hospitals_in_yelahanka():
    sims = [h for h in get_hospitals() if h.get("simulation")]
    assert len(sims) == 10
    assert all(12.95 < h["lat"] < 13.22 and 77.48 < h["lng"] < 77.70 for h in sims)
    assert all(h.get("emergency_available") is not None for h in sims)
    assert all("status" in h and "capacity" in h for h in sims)


def test_cardiac_eligibility_prefers_cardiac_or_icu():
    pool, status = filter_eligible_hospitals(get_hospitals(), dispatch_requirement("cardiac"))
    assert status == "specialty_match"
    names = {h["name"] for h in pool}
    assert "Puttenahalli Community Hospital" not in names
    assert "Avalahalli Trauma & Emergency Hub" in names
    for h in pool:
        specs = set(h.get("specializations") or [])
        if h.get("icu_available"):
            specs.add("ICU")
        assert specs.intersection({"Cardiac", "ICU"})


def test_danger_rating_7_keeps_assigned_hospital():
    cyte = next(h for h in get_hospitals() if h["id"] == 1)
    mission = {
        "simulation": True,
        "ambulance_id": "AMB-104",
        "hospital_id": 1,
        "hospital": cyte,
        "hospital_name": cyte["name"],
        "emergency_category": "cardiac",
        "pickup": {"lat": 13.1344, "lng": 77.5693, "name": "BMSIT"},
        "phase": "pickup",
        "pickup_route": [],
        "is_raining": False,
    }
    maybe_emergency_hospital_reroute(mission, 7, origin=(13.1344, 77.5693))
    assert mission["hospital_id"] == 1
    assert not mission.get("emergency_reroute")


def test_danger_rating_8_selects_nearest_eligible(monkeypatch):
    from app.services import dispatch_optimizer

    def fake_route_full(origin, dest, **_kwargs):
        dist = abs(origin[0] - dest[0]) + abs(origin[1] - dest[1])
        return {
            "duration": max(60.0, dist * 80000.0),
            "coords": [origin, dest],
            "source": "mock",
            "engine": "direct",
            "alternatives": [{"rank": 1, "label": "Route 1", "coords": [origin, dest], "duration": 60, "distance": 1000, "kind": "selected"}],
            "path_sig": f"{dest[0]:.3f}",
        }

    monkeypatch.setattr(dispatch_optimizer.optimizer, "route_full", fake_route_full)
    monkeypatch.setattr(dispatch_optimizer.optimizer, "compute_route", fake_route_full)

    cyte = next(h for h in get_hospitals() if h["id"] == 1)
    origin = (13.1344, 77.5693)
    mission = {
        "simulation": True,
        "ambulance_id": "AMB-104",
        "hospital_id": 1,
        "hospital": cyte,
        "hospital_name": cyte["name"],
        "emergency_category": "cardiac",
        "pickup": {"lat": origin[0], "lng": origin[1], "name": "BMSIT"},
        "phase": "pickup",
        "pickup_route": [],
        "pickup_seconds": 120,
        "is_raining": False,
    }
    maybe_emergency_hospital_reroute(mission, 8, origin=origin)
    assert mission["emergency_reroute"]["danger_rating"] == 8
    assert mission["hospital_id"] != 1
    assert mission["hospital_rerouted"] is True
    chosen = nearest_eligible_hospital(origin, get_hospitals(), dispatch_requirement("cardiac"))
    assert chosen["hospital"]["id"] == mission["hospital_id"]
