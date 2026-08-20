from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.jwt_tokens import decode_supabase_access_token
from app.main import app

SECRET = "test-jwt-secret-do-not-use-in-prod-32b"
ISS = "https://example.supabase.co/auth/v1"
AUD = "authenticated"
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


def _token(
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    email: str = "patient@test.com",
    exp_delta: int = 3600,
    aud: str = AUD,
    iss: str = ISS,
    secret: str = SECRET,
    role: str = "authenticated",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "aud": aud,
        "iss": iss,
        "exp": now + timedelta(seconds=exp_delta),
        "iat": now,
        "user_metadata": {"full_name": "Test User"},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _auth(email: str, sub: str | None = None) -> dict[str, str]:
    uid = sub or {
        "patient@test.com": "11111111-1111-1111-1111-111111111111",
        "staff@test.com": "22222222-2222-2222-2222-222222222222",
        ADMIN_EMAIL: "33333333-3333-3333-3333-333333333333",
    }.get(email, "44444444-4444-4444-4444-444444444444")
    return {"Authorization": f"Bearer {_token(sub=uid, email=email)}"}


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
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", AUD)
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", ISS)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "MAIN_ADMIN_BOOTSTRAP_EMAILS", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "STAFF_BOOTSTRAP_EMAILS", "")
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
def client(jwt_settings):
    with TestClient(app) as c:
        yield c


def test_decode_rejects_expired(jwt_settings):
    token = _token(exp_delta=-10)
    assert decode_supabase_access_token(token) is None


def test_decode_rejects_bad_signature(jwt_settings):
    token = _token(secret="other-secret")
    assert decode_supabase_access_token(token) is None


def test_decode_rejects_wrong_audience(jwt_settings):
    token = _token(aud="other")
    assert decode_supabase_access_token(token) is None


def test_decode_accepts_valid(jwt_settings):
    token = _token()
    user = decode_supabase_access_token(token)
    assert user is not None
    assert user["email"] == "patient@test.com"
    assert user["id"] == "11111111-1111-1111-1111-111111111111"


def test_missing_token_is_401(client):
    res = client.get("/accounts/me")
    assert res.status_code == 401


def test_expired_token_is_401(client):
    res = client.get("/accounts/me", headers={"Authorization": f"Bearer {_token(exp_delta=-5)}"})
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
