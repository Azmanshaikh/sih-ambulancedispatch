from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.supabase import rest_insert, rest_select, rest_update, rest_upsert, supabase_client

_profiles: dict[str, dict[str, Any]] = {}
_requests: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_profile(user_id: str, email: str, full_name: str | None, bootstrap_staff: bool = False) -> dict[str, Any]:
    existing = get_profile(user_id)
    if existing:
        if bootstrap_staff and (existing.get("role") != "staff" or existing.get("status") != "active"):
            existing["role"] = "staff"
            existing["status"] = "active"
            existing["requested_role"] = None
            _save_profile(existing)
        return existing

    role = "staff" if bootstrap_staff else "patient"
    row = {
        "id": user_id,
        "email": email,
        "full_name": full_name or email.split("@")[0],
        "role": role,
        "status": "active" if bootstrap_staff else "pending",
        "requested_role": None,
        "ambulance_id": None,
        "hospital_id": None,
        "onboarded": True if bootstrap_staff else False,
        "updated_at": _now(),
    }
    _save_profile(row)
    return row


def get_profile(user_id: str) -> dict[str, Any] | None:
    prev = _profiles.get(user_id) or {}
    row = None
    if supabase_client is not None:
        try:
            res = supabase_client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
            if res.data:
                row = res.data[0]
        except Exception:
            row = None
    if row is None:
        rows = rest_select("profiles", {"id": f"eq.{user_id}", "select": "*"})
        row = rows[0] if rows else None
    if row is None:
        return prev or None
    if "onboarded" in prev:
        row["onboarded"] = prev["onboarded"]
    else:
        row.setdefault("onboarded", False)
    if row.get("hospital_id") is None and prev.get("hospital_id") is not None:
        row["hospital_id"] = prev["hospital_id"]
    _profiles[user_id] = row
    return row


_DB_KEYS = {"id", "email", "full_name", "role", "status", "requested_role", "ambulance_id", "hospital_id", "updated_at"}


def _db_payload(row: dict[str, Any], include_hospital: bool = True) -> dict[str, Any]:
    keys = _DB_KEYS if include_hospital else _DB_KEYS - {"hospital_id"}
    payload = {k: row.get(k) for k in keys}
    if include_hospital:
        hid = payload.get("hospital_id")
        if hid is None or hid == "":
            payload["hospital_id"] = None
        else:
            try:
                payload["hospital_id"] = int(hid)
            except (TypeError, ValueError):
                payload["hospital_id"] = None
    return payload


def _save_profile(row: dict[str, Any]) -> dict[str, Any]:
    row["updated_at"] = _now()
    _profiles[row["id"]] = row
    payload = _db_payload(row, include_hospital=True)
    saved = False
    if supabase_client is not None:
        try:
            supabase_client.table("profiles").upsert(payload).execute()
            saved = True
        except Exception:
            saved = False
    if not saved:
        saved = rest_upsert("profiles", payload) is not None
    if not saved:
        slim = _db_payload(row, include_hospital=False)
        if supabase_client is not None:
            try:
                supabase_client.table("profiles").upsert(slim).execute()
                saved = True
            except Exception:
                saved = False
        if not saved:
            rest_upsert("profiles", slim)
    return row


def list_profiles() -> list[dict[str, Any]]:
    if supabase_client is not None:
        try:
            res = supabase_client.table("profiles").select("*").execute()
            if res.data is not None:
                for row in res.data:
                    _profiles[row["id"]] = row
                return list(res.data)
        except Exception:
            pass
    rows = rest_select("profiles", {"select": "*"})
    if rows:
        for row in rows:
            _profiles[row["id"]] = row
        return rows
    return list(_profiles.values())


def request_role(user_id: str, requested_role: str) -> dict[str, Any]:
    if requested_role not in ("driver", "staff", "doctor"):
        raise ValueError("requested_role must be driver, staff, or doctor")
    profile = get_profile(user_id)
    if not profile:
        raise ValueError("profile missing")
    if profile.get("role") == requested_role and profile.get("status") == "active":
        return profile

    req = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "requested_role": requested_role,
        "status": "pending",
        "reviewed_by": None,
        "created_at": _now(),
        "reviewed_at": None,
        "email": profile.get("email"),
        "full_name": profile.get("full_name"),
    }
    profile["requested_role"] = requested_role
    _save_profile(profile)

    inserted = None
    if supabase_client is not None:
        try:
            payload = {k: req[k] for k in ("user_id", "requested_role", "status", "reviewed_by", "created_at", "reviewed_at")}
            res = supabase_client.table("role_requests").insert(payload).execute()
            if res.data:
                inserted = res.data[0]
        except Exception:
            inserted = None
    if inserted is None:
        payload = {k: req[k] for k in ("user_id", "requested_role", "status", "reviewed_by", "created_at", "reviewed_at")}
        inserted = rest_insert("role_requests", payload)
    if inserted:
        req["id"] = inserted.get("id", req["id"])
    else:
        _requests.append(req)
    return req


def list_requests(status: str | None = "pending") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if supabase_client is not None:
        try:
            q = supabase_client.table("role_requests").select("*")
            if status:
                q = q.eq("status", status)
            res = q.order("created_at", desc=True).execute()
            rows = list(res.data or [])
        except Exception:
            rows = []
    if not rows:
        params = {"select": "*", "order": "created_at.desc"}
        if status:
            params["status"] = f"eq.{status}"
        rows = rest_select("role_requests", params)
    if not rows:
        rows = [r for r in _requests if status is None or r["status"] == status]

    profiles = {p["id"]: p for p in list_profiles()}
    for row in rows:
        p = profiles.get(row.get("user_id")) or {}
        row["email"] = p.get("email") or row.get("email")
        row["full_name"] = p.get("full_name") or row.get("full_name")
    return rows


def decide_request(request_id: str | int, reviewer_id: str, approve: bool, ambulance_id: str | None = None) -> dict[str, Any]:
    row = None
    if supabase_client is not None:
        try:
            res = supabase_client.table("role_requests").select("*").eq("id", request_id).limit(1).execute()
            if res.data:
                row = res.data[0]
        except Exception:
            row = None
    if row is None:
        found = rest_select("role_requests", {"id": f"eq.{request_id}", "select": "*"})
        row = found[0] if found else None
    if row is None:
        row = next((r for r in _requests if str(r["id"]) == str(request_id)), None)
    if not row:
        raise ValueError("request not found")

    new_status = "approved" if approve else "denied"
    row["status"] = new_status
    row["reviewed_by"] = reviewer_id
    row["reviewed_at"] = _now()

    profile = get_profile(row["user_id"])
    if profile and approve:
        profile["role"] = row["requested_role"]
        profile["status"] = "active"
        profile["requested_role"] = None
        if row["requested_role"] in ("driver", "doctor") and ambulance_id:
            profile["ambulance_id"] = ambulance_id
        _save_profile(profile)
    elif profile and not approve:
        profile["requested_role"] = None
        _save_profile(profile)

    if supabase_client is not None:
        try:
            supabase_client.table("role_requests").update(
                {"status": new_status, "reviewed_by": reviewer_id, "reviewed_at": row["reviewed_at"]}
            ).eq("id", request_id).execute()
        except Exception:
            rest_update(
                "role_requests",
                {"id": f"eq.{request_id}"},
                {"status": new_status, "reviewed_by": reviewer_id, "reviewed_at": row["reviewed_at"]},
            )
    else:
        rest_update(
            "role_requests",
            {"id": f"eq.{request_id}"},
            {"status": new_status, "reviewed_by": reviewer_id, "reviewed_at": row["reviewed_at"]},
        )
    return {"request": row, "profile": profile}


def activate_patient(user_id: str) -> dict[str, Any]:
    profile = get_profile(user_id)
    if not profile:
        raise ValueError("profile missing")
    profile["role"] = "patient"
    profile["status"] = "active"
    profile["requested_role"] = None
    profile["onboarded"] = True
    return _save_profile(profile)


def activate_verified_role(
    user_id: str,
    role: str,
    ambulance_id: str | None = None,
    hospital_id: int | None = None,
) -> dict[str, Any]:
    profile = get_profile(user_id)
    if not profile:
        raise ValueError("profile missing")
    if role not in ("driver", "staff", "doctor"):
        raise ValueError("invalid role")
    profile["role"] = role
    profile["status"] = "active"
    profile["requested_role"] = None
    profile["onboarded"] = True
    if role in ("driver", "doctor") and ambulance_id:
        profile["ambulance_id"] = ambulance_id
    if role == "staff":
        hid = hospital_id if hospital_id is not None else profile.get("hospital_id")
        try:
            profile["hospital_id"] = int(hid) if hid is not None and hid != "" else None
        except (TypeError, ValueError):
            profile["hospital_id"] = None
    return _save_profile(profile)


def mark_otp_pending(user_id: str, requested_role: str, hospital_id: int | None = None) -> dict[str, Any]:
    profile = get_profile(user_id)
    if not profile:
        raise ValueError("profile missing")
    profile["status"] = "pending"
    profile["requested_role"] = requested_role
    if requested_role not in ("driver", "doctor"):
        profile["ambulance_id"] = None
    if requested_role == "staff":
        try:
            profile["hospital_id"] = int(hospital_id) if hospital_id is not None else None
        except (TypeError, ValueError):
            profile["hospital_id"] = None
    elif requested_role in ("driver", "doctor"):
        profile["hospital_id"] = None
    return _save_profile(profile)


def set_driver_ambulance(user_id: str, ambulance_id: str | None) -> dict[str, Any]:
    profile = get_profile(user_id)
    if not profile:
        raise ValueError("profile missing")
    profile["ambulance_id"] = ambulance_id
    return _save_profile(profile)
