from __future__ import annotations

import pytest

from app.services import graph_router


def test_traffic_density_labels_and_costs():
    assert graph_router._taps_label(1) == "Low"
    assert graph_router._taps_label(2) == "Moderate"
    assert graph_router._taps_label(3) == "High"
    assert graph_router._taps_label(4) == "Severe"
    assert graph_router._taps_mult(1) < graph_router._taps_mult(2) < graph_router._taps_mult(3)
    assert graph_router._taps_mult(4) > graph_router._taps_mult(3)


@pytest.mark.skipif(not graph_router.available(), reason="networkx not installed")
def test_simulated_traffic_switches_fastest_path(monkeypatch):
    origin = (13.1344, 77.5693)
    dest = (13.1168, 77.5819)
    via_a = (13.1280, 77.5720)
    via_b = (13.1280, 77.5950)
    path_a = [origin, via_a, dest]
    path_b = [origin, via_b, dest]

    def fake_candidates(*_args, **_kwargs):
        return (
            [
                {"coords": path_a, "duration": 100.0, "distance": 2200.0},
                {"coords": path_b, "duration": 160.0, "distance": 3400.0},
            ],
            "mock",
        )

    monkeypatch.setattr(graph_router, "_fetch_candidates", fake_candidates)

    baseline = graph_router.route(origin, dest, prefer="fastest", enrich=True)
    assert baseline is not None
    congested = graph_router.route(
        origin,
        dest,
        prefer="fastest",
        enrich=True,
        traffic_points=[{"lat": via_a[0], "lng": via_a[1], "taps": 4}],
    )
    assert congested is not None
    assert congested["path_sig"] != baseline["path_sig"]
    assert congested["sim_traffic"]
    assert congested["duration"] > 0
    assert baseline.get("alternatives")
    assert baseline["alternatives"][0]["kind"] == "selected"
    assert len(baseline["alternatives"]) >= 2
