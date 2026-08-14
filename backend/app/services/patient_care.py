from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.core.supabase import rest_insert, rest_select, rest_upsert
from app.services.runtime_state import get_vitals, push_alert

_profiles: dict[str, dict[str, Any]] = {}
_chats: dict[str, list[dict[str, Any]]] = {}
_reports: list[dict[str, Any]] = []
_tavus_owners: dict[str, str] = {}
_tavus_ingested: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_health_profile(user_id: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "user_id": user_id,
        "allergies": "",
        "medicines": "",
        "conditions": "",
        "cardiac": False,
        "diabetes": False,
        "epilepsy": False,
        "pregnant": False,
        "visits": [],
        "doctors": [],
        "notes": "",
        "updated_at": _now(),
    }


def get_health_profile(user_id: str) -> dict[str, Any]:
    if user_id in _profiles:
        return dict(_profiles[user_id])
    rows = rest_select("patient_health_profiles", {"id": f"eq.{user_id}", "select": "*"})
    if rows:
        row = rows[0]
        row.setdefault("visits", [])
        row.setdefault("doctors", [])
        _profiles[user_id] = row
        return dict(row)
    return empty_health_profile(user_id)


def save_health_profile(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_health_profile(user_id)
    visits = payload.get("visits") if isinstance(payload.get("visits"), list) else current.get("visits") or []
    doctors = payload.get("doctors") if isinstance(payload.get("doctors"), list) else current.get("doctors") or []
    row = {
        "id": user_id,
        "user_id": user_id,
        "allergies": payload.get("allergies", current.get("allergies") or ""),
        "medicines": payload.get("medicines", current.get("medicines") or ""),
        "conditions": payload.get("conditions", current.get("conditions") or ""),
        "cardiac": bool(payload.get("cardiac", current.get("cardiac"))),
        "diabetes": bool(payload.get("diabetes", current.get("diabetes"))),
        "epilepsy": bool(payload.get("epilepsy", current.get("epilepsy"))),
        "pregnant": bool(payload.get("pregnant", current.get("pregnant"))),
        "visits": visits,
        "doctors": doctors,
        "notes": payload.get("notes", current.get("notes") or ""),
        "updated_at": _now(),
    }
    _profiles[user_id] = row
    rest_upsert("patient_health_profiles", row)
    return dict(row)


def list_chat(user_id: str, limit: int = 80) -> list[dict[str, Any]]:
    mem = list(_chats.get(user_id) or [])
    rows = rest_select(
        "patient_chat_messages",
        {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.asc"},
    )
    if rows:
        merged = [{
            "id": r.get("id"),
            "role": r.get("role"),
            "content": r.get("content"),
            "created_at": r.get("created_at"),
        } for r in rows]
        return merged[-limit:]
    return mem[-limit:]


def append_chat(user_id: str, role: str, content: str) -> dict[str, Any]:
    turn = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": _now(),
    }
    _chats.setdefault(user_id, []).append(turn)
    _chats[user_id] = _chats[user_id][-120:]
    rest_insert(
        "patient_chat_messages",
        {
            "id": turn["id"],
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": turn["created_at"],
        },
    )
    return turn


async def nemotron_chat(messages: list[dict[str, str]], max_tokens: int = 500) -> str:
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not configured")
    payload = {
        "model": settings.NVIDIA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.NVIDIA_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60.0,
        )
    if response.status_code != 200:
        raise RuntimeError(response.text[:400])
    result = response.json()
    return (result.get("choices") or [{}])[0].get("message", {}).get("content") or ""


VOICE_SYSTEM = (
    "You are JEEVAN, a calm nurse-style helper on a live voice call. "
    "Give short spoken remedies for small everyday issues: headache, mild fever, "
    "acidity, dehydration, sleep, cough, diet. Use 3-6 short sentences. "
    "You are not a doctor. If it sounds urgent or severe, tell them to tap Emergency SOS. "
    "Do not use markdown or lists with stars. Speak naturally."
)


async def gemini_chat(user_id: str, message: str) -> str:
    key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    history = list_chat(user_id, limit=12)
    contents: list[dict[str, Any]] = []
    for turn in history:
        role = "model" if turn.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": turn.get("content") or ""}]})
    contents.append({"role": "user", "parts": [{"text": message.strip()}]})
    model = (settings.GEMINI_MODEL or "gemini-2.0-flash").strip()
    payload = {
        "system_instruction": {"parts": [{"text": VOICE_SYSTEM}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 280},
    }
    models = [model, "gemini-2.0-flash", "gemini-1.5-flash"]
    seen: set[str] = set()
    last_error = ""
    async with httpx.AsyncClient() as client:
        for name in models:
            if name in seen:
                continue
            seen.add(name)
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent",
                params={"key": key},
                json=payload,
                timeout=45.0,
            )
            if response.status_code == 200:
                data = response.json()
                parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
                text = "".join(p.get("text") or "" for p in parts).strip()
                if text:
                    return text
            last_error = response.text[:400]
            if response.status_code not in (404, 400):
                break
    raise RuntimeError(last_error or "Gemini voice failed")


TAVUS_CONTEXT = (
    "You are JEEVAN, a live video-call health helper. You can hear the patient. "
    "Listen until they finish. Think for a moment, then answer out loud with simple "
    "home remedies for small issues (headache, mild fever, acidity, dehydration, sleep, cough, diet). "
    "Speak in short sentences. You are not a doctor. If it sounds urgent, tell them to tap Emergency SOS."
)


def _tavus_context_for_user(user_id: str, patient_name: str | None) -> str:
    profile = get_health_profile(user_id)
    prior = list_chat(user_id, limit=16)
    chat_bits = "\n".join(
        f"{t.get('role')}: {t.get('content')}" for t in prior if t.get("content")
    )
    return (
        f"{TAVUS_CONTEXT}\n"
        f"Patient name: {patient_name or 'unknown'}.\n"
        f"Known allergies: {profile.get('allergies') or 'none noted'}.\n"
        f"Medicines: {profile.get('medicines') or 'none noted'}.\n"
        f"Conditions: {profile.get('conditions') or 'none noted'}.\n"
        f"Prior notes from app chat (use if relevant):\n{chat_bits or '(none yet)'}"
    )


async def start_tavus_conversation(user_id: str, patient_name: str | None = None) -> dict[str, Any]:
    if not settings.TAVUS_API_KEY:
        raise RuntimeError("TAVUS_API_KEY not configured")
    replica = (settings.TAVUS_REPLICA_ID or settings.TAVUS_FACE_ID or "r90bbd427f71").strip()
    pal = (settings.TAVUS_PAL_ID or "").strip() or None
    persona = (settings.TAVUS_PERSONA_ID or "").strip() or None
    face = (settings.TAVUS_FACE_ID or "").strip() or None
    payload: dict[str, Any] = {
        "conversation_name": f"JEEVAN health call · {patient_name or 'patient'}",
        "conversational_context": _tavus_context_for_user(user_id, patient_name),
        "custom_greeting": (
            f"Hello{(' ' + patient_name) if patient_name else ''}. I am Jeevan. "
            "I can hear you. Tell me your small health issue, I will think, then suggest simple remedies. "
            "If it feels serious, use Emergency SOS in the app."
        ),
    }
    if pal:
        payload["pal_id"] = pal
        if face or replica:
            payload["face_id"] = face or replica
    elif persona:
        payload["persona_id"] = persona
        payload["replica_id"] = replica
    else:
        payload["replica_id"] = replica
        if face:
            payload["face_id"] = face
    callback = (settings.TAVUS_CALLBACK_URL or "").strip()
    if callback:
        payload["callback_url"] = callback
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://tavusapi.com/v2/conversations",
            headers={"x-api-key": settings.TAVUS_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
    data = response.json() if response.content else {}
    if response.status_code >= 400:
        raise RuntimeError(str(data.get("message") or data.get("error") or data)[:400])
    url = data.get("conversation_url")
    cid = str(data.get("conversation_id") or "")
    if not url or not cid:
        raise RuntimeError("Tavus did not return a conversation_url")
    _tavus_owners[cid] = user_id
    return {
        "conversation_id": cid,
        "conversation_url": url,
        "status": data.get("status"),
    }


def ingest_tavus_transcript(conversation_id: str, transcript: list[Any], user_id: str | None = None) -> int:
    uid = user_id or _tavus_owners.get(conversation_id)
    if not uid or not transcript:
        return 0
    saved = 0
    for turn in transcript:
        if not isinstance(turn, dict):
            continue
        role = (turn.get("role") or "user").lower()
        if role in ("replica", "model", "pal", "persona"):
            role = "assistant"
        if role not in ("user", "assistant"):
            continue
        content = (turn.get("content") or turn.get("text") or "").strip()
        if not content:
            continue
        key = f"{conversation_id}:{role}:{content[:160]}"
        if key in _tavus_ingested:
            continue
        _tavus_ingested.add(key)
        append_chat(uid, role, content)
        saved += 1
    return saved


def _extract_transcript(payload: dict[str, Any]) -> list[Any]:
    props = payload.get("properties") or {}
    if isinstance(props.get("transcript"), list):
        return props["transcript"]
    if isinstance(payload.get("transcript"), list):
        return payload["transcript"]
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        if event.get("event_type") == "application.transcription_ready":
            inner = event.get("properties") or event
            if isinstance(inner.get("transcript"), list):
                return inner["transcript"]
    return []


async def fetch_tavus_transcript(conversation_id: str) -> list[Any]:
    if not settings.TAVUS_API_KEY:
        return []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://tavusapi.com/v2/conversations/{conversation_id}",
            params={"verbose": "true"},
            headers={"x-api-key": settings.TAVUS_API_KEY},
            timeout=20.0,
        )
    if response.status_code >= 400:
        return []
    data = response.json() if response.content else {}
    return _extract_transcript(data)


async def end_tavus_conversation(conversation_id: str) -> dict[str, Any]:
    if not settings.TAVUS_API_KEY or not conversation_id:
        return {"saved": 0}
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://tavusapi.com/v2/conversations/{conversation_id}/end",
            headers={"x-api-key": settings.TAVUS_API_KEY},
            timeout=15.0,
        )
    saved = 0
    for delay in (2.0, 3.0, 5.0):
        await asyncio.sleep(delay)
        turns = await fetch_tavus_transcript(conversation_id)
        saved = ingest_tavus_transcript(conversation_id, turns)
        if saved:
            break
    return {"saved": saved, "conversation_id": conversation_id}


def _profile_text(profile: dict[str, Any]) -> str:
    flags = []
    if profile.get("cardiac"):
        flags.append("cardiac")
    if profile.get("diabetes"):
        flags.append("diabetes")
    if profile.get("epilepsy"):
        flags.append("epilepsy")
    if profile.get("pregnant"):
        flags.append("pregnant")
    visits = profile.get("visits") or []
    visit_lines = [
        f"- {v.get('hospital') or 'Unknown'} ({v.get('when') or 'date n/a'}): {v.get('reason') or ''}"
        for v in visits if isinstance(v, dict)
    ]
    doctors = profile.get("doctors") or []
    doc_lines = [
        f"- {d.get('name') or 'Unknown'} ({d.get('specialty') or 'specialty n/a'}): {d.get('notes') or ''}"
        for d in doctors if isinstance(d, dict)
    ]
    return (
        f"Allergies: {profile.get('allergies') or 'none noted'}\n"
        f"Medicines: {profile.get('medicines') or 'none noted'}\n"
        f"Conditions: {profile.get('conditions') or 'none noted'}\n"
        f"Flags: {', '.join(flags) or 'none'}\n"
        f"Notes: {profile.get('notes') or 'none'}\n"
        f"Previous hospital visits:\n{chr(10).join(visit_lines) or '- none'}\n"
        f"Doctors consulted:\n{chr(10).join(doc_lines) or '- none'}"
    )


def _chat_text(user_id: str) -> str:
    turns = list_chat(user_id, limit=30)
    if not turns:
        return "(no everyday chat history)"
    return "\n".join(f"{t.get('role')}: {t.get('content')}" for t in turns)


def fallback_report(mission: dict[str, Any], profile: dict[str, Any], vitals: dict[str, Any], chat: str) -> str:
    name = mission.get("patient_name") or "Patient"
    hospital = mission.get("hospital_name") or "hospital"
    return (
        f"JEEVAN handover for {name}\n"
        f"Destination: {hospital} · Unit {mission.get('ambulance_id') or 'n/a'}\n\n"
        f"{_profile_text(profile)}\n\n"
        f"Latest vitals: HR {vitals.get('heart_rate')} bpm, SpO2 {vitals.get('spo2')}%, "
        f"BP {vitals.get('bp_sys')}/{vitals.get('bp_dia')}, temp {vitals.get('temperature_c')} C, "
        f"resp {vitals.get('resp_rate')}/min.\n\n"
        f"Everyday chat and video-call notes:\n{chat}\n\n"
        "This is an operational handover, not a diagnosis. Confirm allergies and medicines with the patient."
    )


async def generate_trip_report(mission: dict[str, Any]) -> dict[str, Any]:
    patient_id = mission.get("patient_id") or ""
    profile = get_health_profile(patient_id) if patient_id else empty_health_profile("")
    vitals = get_vitals(patient_id) if patient_id else {}
    chat = _chat_text(patient_id) if patient_id else "(none)"
    prompt = (
        "Write a concise ER handover report for ambulance staff. Not a diagnosis. "
        "Use only the facts given. Sections: Patient, This trip, Allergies, Medicines, "
        "Conditions, Prior hospital visits, Doctors consulted, Recent everyday complaints from chat, "
        "Latest vitals, Cautions for ER.\n\n"
        f"Patient: {mission.get('patient_name')} ({mission.get('patient_email')})\n"
        f"Pickup: {(mission.get('pickup') or {}).get('name')}\n"
        f"Hospital: {mission.get('hospital_name')}\n"
        f"Unit: {mission.get('ambulance_id')}\n"
        f"ETA minutes: {mission.get('eta_minutes')}\n\n"
        f"Health profile:\n{_profile_text(profile)}\n\n"
        f"Vitals: {vitals}\n\n"
        f"Chat:\n{chat}"
    )
    text = ""
    try:
        text = (await nemotron_chat(
            [
                {"role": "system", "content": "You are JEEVAN, writing ambulance-to-hospital handover notes."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=900,
        )).strip()
    except Exception:
        text = ""
    if not text:
        text = fallback_report(mission, profile, vitals, chat)
    row = {
        "id": str(uuid.uuid4()),
        "mission_id": mission.get("id"),
        "patient_id": patient_id or None,
        "patient_name": mission.get("patient_name"),
        "patient_email": mission.get("patient_email"),
        "hospital_name": mission.get("hospital_name"),
        "ambulance_id": mission.get("ambulance_id"),
        "body": text,
        "created_at": _now(),
    }
    _reports.insert(0, row)
    _reports[:] = _reports[:80]
    rest_insert(
        "trip_reports",
        {
            **row,
            "patient_id": patient_id if patient_id else None,
        },
    )
    push_alert(
        "staff",
        "TRIP REPORT READY",
        f"Handover for {mission.get('patient_name') or 'patient'} at {mission.get('hospital_name') or 'hospital'} is ready.",
        ambulance_id=mission.get("ambulance_id"),
        mission_id=mission.get("id"),
        extra={"report_id": row["id"]},
    )
    return row


def list_reports_for(user: dict[str, Any]) -> list[dict[str, Any]]:
    role = (user.get("profile") or {}).get("role")
    uid = user.get("id")
    db = rest_select("trip_reports", {"select": "*", "order": "created_at.desc", "limit": "40"})
    merged: dict[str, dict[str, Any]] = {str(r.get("id")): r for r in db}
    for r in _reports:
        merged[str(r.get("id"))] = r
    rows = sorted(merged.values(), key=lambda a: a.get("created_at") or "", reverse=True)
    if role == "staff":
        return rows
    return [r for r in rows if str(r.get("patient_id") or "") == str(uid)]
