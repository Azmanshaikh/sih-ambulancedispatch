from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

ADMIN_EMAIL = "admin@test.com"
SIM_BODY = {
    "pickup_lat": 13.13,
    "pickup_lng": 77.56,
    "dest_lat": 13.11,
    "dest_lng": 77.58,
    "ambulance_id": "AMB-101",
    "push_to_driver": False,
}

_PROFILES: dict[str, dict[str, Any]] = {}
_UIDS = {
    "patient@test.com": "11111111-1111-1111-1111-111111111111",
    "staff@test.com": "22222222-2222-2222-2222-222222222222",
    ADMIN_EMAIL: "33333333-3333-3333-3333-333333333333",
}


def _auth(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def fake_auth_user_from_token(access_token: str) -> dict[str, Any] | None:
    if not access_token or access_token in ("expired", "invalid"):
        return None
    email = access_token.strip()
    uid = _UIDS.get(email)
    if not uid:
        return None
    return {"id": uid, "email": email, "user_metadata": {"full_name": "Test User"}}


def fake_ensure_profile(
    user_id: str,
    email: str,
    full_name: str | None,
    bootstrap_staff: bool = False,
    bootstrap_main_admin: bool = False,
) -> dict[str, Any]:
    override = _PROFILES.get(str(email).lower())
    if override:
        row = dict(override)
        row["id"] = user_id
        row["email"] = email
        return row
    role = "patient"
    if bootstrap_main_admin:
        role = "main_admin"
    elif bootstrap_staff:
        role = "staff"
    return {
        "id": user_id,
        "email": email,
        "full_name": full_name or email,
        "role": role,
        "status": "active",
        "onboarded": True,
        "requested_role": None,
        "ambulance_id": None,
        "hospital_id": None,
    }


@pytest.fixture
def oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "MAIN_ADMIN_BOOTSTRAP_EMAILS", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "STAFF_BOOTSTRAP_EMAILS", "")
    monkeypatch.setattr("app.core.security.auth_user_from_token", fake_auth_user_from_token)
    monkeypatch.setattr("app.core.security.ensure_profile", fake_ensure_profile)
    monkeypatch.setattr(
        "app.core.security.demote_main_admin",
        lambda user_id, fallback_staff=False: fake_ensure_profile(user_id, "x@test.com", None),
    )
    _PROFILES.clear()
    _PROFILES["patient@test.com"] = {
        "role": "patient",
        "status": "active",
        "onboarded": True,
        "requested_role": None,
        "ambulance_id": None,
        "hospital_id": None,
        "full_name": "Patient",
    }
    _PROFILES["staff@test.com"] = {
        "role": "staff",
        "status": "active",
        "onboarded": True,
        "requested_role": None,
        "ambulance_id": None,
        "hospital_id": None,
        "full_name": "Staff",
    }
    _PROFILES[ADMIN_EMAIL] = {
        "role": "main_admin",
        "status": "active",
        "onboarded": True,
        "requested_role": None,
        "ambulance_id": None,
        "hospital_id": None,
        "full_name": "Admin",
    }


@pytest.fixture
def client(oauth_settings):
    with TestClient(app) as c:
        yield c


def test_missing_token_is_401(client):
    res = client.get("/accounts/me")
    assert res.status_code == 401


def test_invalid_session_is_401(client):
    res = client.get("/accounts/me", headers={"Authorization": "Bearer expired"})
    assert res.status_code == 401


def test_valid_patient_can_read_me(client):
    res = client.get("/accounts/me", headers=_auth("patient@test.com"))
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "patient"


def test_patient_cannot_access_fleet(client):
    res = client.get("/tracking/fleet", headers=_auth("patient@test.com"))
    assert res.status_code == 403


def test_patient_cannot_access_admin_simulation(client):
    res = client.post("/tracking/admin/simulate-route", json=SIM_BODY, headers=_auth("patient@test.com"))
    assert res.status_code == 403


def test_staff_cannot_access_admin_simulation(client):
    res = client.post("/tracking/admin/simulate-route", json=SIM_BODY, headers=_auth("staff@test.com"))
    assert res.status_code == 403


def test_choose_role_rejects_main_admin_payload(client):
    res = client.post(
        "/accounts/choose-role",
        json={"role": "main_admin"},
        headers=_auth("patient@test.com"),
    )
    assert res.status_code == 422


def test_patient_cannot_read_other_health_profile(client):
    res = client.get(
        "/accounts/health-profile",
        params={"patient_id": "99999999-9999-9999-9999-999999999999"},
        headers=_auth("patient@test.com"),
    )
    assert res.status_code == 403


def test_main_admin_can_call_simulation(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.tracking.simulate_custom_route",
        lambda *args, **kwargs: {
            "pickup_route": [],
            "route": [],
            "eta_minutes": 4,
            "pickup_minutes": 2,
            "transport_minutes": 2,
        },
    )
    monkeypatch.setattr("app.api.tracking.is_raining_at", lambda *args, **kwargs: False)
    res = client.post("/tracking/admin/simulate-route", json=SIM_BODY, headers=_auth(ADMIN_EMAIL))
    assert res.status_code == 200
    assert res.json()["status"] == "success"
