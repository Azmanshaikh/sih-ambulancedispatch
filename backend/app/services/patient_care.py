from __future__ import annotations

import asyncio
import base64
import json
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
_medical_analyses: dict[str, list[dict[str, Any]]] = {}
_tavus_owners: dict[str, str] = {}
_tavus_ingested: set[str] = set()
_call_intakes: dict[str, dict[str, Any]] = {}


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


def _uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        uuid.UUID(str(value))
        return str(value)
    except Exception:
        return None


def _remember_tavus_owner(conversation_id: str, user_id: str) -> None:
    cid = (conversation_id or "").strip()
    uid = _uuid_or_none(user_id)
    if not cid or not uid:
        return
    _tavus_owners[cid] = uid
    rest_insert(
        "tavus_conversations",
        {"conversation_id": cid, "user_id": uid, "created_at": _now()},
    )


def _tavus_owner(conversation_id: str) -> str | None:
    cid = (conversation_id or "").strip()
    if not cid:
        return None
    owner = _tavus_owners.get(cid)
    if owner:
        return owner
    rows = rest_select(
        "tavus_conversations",
        {"conversation_id": f"eq.{cid}", "select": "user_id", "limit": "1"},
    )
    uid = _uuid_or_none((rows or [{}])[0].get("user_id") if rows else None)
    if uid:
        _tavus_owners[cid] = uid
    return uid


def save_medical_analysis(
    user_id: str,
    email: str | None,
    input_text: str,
    analysis: str,
    image_name: str | None = None,
) -> dict[str, Any]:
    """Persist an AI report analysis against the signed-in account."""
    row = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "email": email or "",
        "input_text": (input_text or "")[:8000],
        "analysis": analysis or "",
        "image_name": image_name or "",
        "created_at": _now(),
    }
    bucket = _medical_analyses.setdefault(user_id, [])
    bucket.append(row)
    _medical_analyses[user_id] = bucket[-40:]
    rest_insert(
        "medical_reports",
        {
            "id": row["id"],
            "user_id": _uuid_or_none(user_id),
            "email": row["email"] or None,
            "input_text": row["input_text"],
            "analysis": row["analysis"],
            "image_name": row["image_name"] or None,
            "created_at": row["created_at"],
        },
    )
    try:
        profile = get_health_profile(user_id)
        stamp = f"[{row['created_at'][:16]}] AI report analysis"
        if image_name:
            stamp += f" ({image_name})"
        snippet = (analysis or "").strip()[:1200]
        notes = (profile.get("notes") or "").strip()
        profile["notes"] = f"{notes}\n\n{stamp}\n{snippet}".strip() if notes else f"{stamp}\n{snippet}"
        visits = list(profile.get("visits") or [])
        visits.append({"hospital": "Uploaded report", "when": row["created_at"][:10], "reason": snippet[:240]})
        profile["visits"] = visits[-20:]
        save_health_profile(user_id, profile)
    except Exception as exc:
        print("health profile stamp skipped:", exc)
    return row


def list_medical_analyses(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = rest_select(
        "medical_reports",
        {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc", "limit": str(limit)},
    )
    if rows:
        return rows[:limit]
    mem = list(_medical_analyses.get(user_id) or [])
    mem.reverse()
    return mem[:limit]


def list_chat(user_id: str, limit: int = 80) -> list[dict[str, Any]]:
    uid = _uuid_or_none(user_id)
    if not uid:
        return []
    mem = [t for t in (_chats.get(uid) or []) if str(t.get("user_id") or "") == uid]
    rows = rest_select(
        "patient_chat_messages",
        {
            "user_id": f"eq.{uid}",
            "select": "id,user_id,role,content,created_at",
            "order": "created_at.asc",
            "limit": str(max(limit, 80)),
        },
    )
    owned = [
        {
            "id": r.get("id"),
            "user_id": uid,
            "role": r.get("role"),
            "content": r.get("content"),
            "created_at": r.get("created_at"),
        }
        for r in (rows or [])
        if str(r.get("user_id") or "") == uid
    ]
    if owned:
        return owned[-limit:]
    return mem[-limit:]


def append_chat(user_id: str, role: str, content: str) -> dict[str, Any]:
    uid = _uuid_or_none(user_id)
    if not uid:
        raise RuntimeError("Signed-in account required to save chat")
    turn = {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "role": role,
        "content": content,
        "created_at": _now(),
    }
    _chats.setdefault(uid, []).append(turn)
    _chats[uid] = [t for t in _chats[uid] if str(t.get("user_id") or "") == uid][-120:]
    rest_insert(
        "patient_chat_messages",
        {
            "id": turn["id"],
            "user_id": uid,
            "role": role,
            "content": content,
            "created_at": turn["created_at"],
        },
    )
    return turn


def _nvidia_models() -> list[str]:
    models = [settings.NVIDIA_MODEL]
    for name in (settings.NVIDIA_MODEL_FALLBACKS or "").split(","):
        name = name.strip()
        if name and name not in models:
            models.append(name)
    return models


def _nvidia_asr_models() -> list[str]:
    models: list[str] = []
    for name in (settings.NVIDIA_ASR_MODEL, *(settings.NVIDIA_ASR_MODEL_FALLBACKS or "").split(",")):
        name = (name or "").strip()
        if name and name not in models:
            models.append(name)
    return models


def _transcript_text(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.strip("`").strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    low = text.lower().strip(" .")
    if low in {"empty", "n/a", "na", "silence", "[silence]", "no speech", "none"}:
        return ""
    return text


async def nvidia_transcribe(audio_bytes: bytes, mime_type: str = "audio/wav", language: str = "en") -> str:
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not configured")
    models = _nvidia_asr_models()
    if not models:
        raise RuntimeError("NVIDIA_ASR_MODEL is not set to a speech-capable model")
    lang_name = {"en": "English", "hi": "Hindi", "kn": "Kannada"}.get((language or "en")[:2], "English")
    mime = (mime_type or "audio/wav").split(";")[0].strip() or "audio/wav"
    if mime not in ("audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3"):
        mime = "audio/wav"
    data_url = f"data:{mime};base64,{base64.b64encode(audio_bytes).decode('ascii')}"
    prompt = (
        f"Transcribe this spoken audio into {lang_name} text. "
        "Reply with only the spoken words, no quotes, labels, or commentary. "
        "If there is no speech, reply with EMPTY."
    )
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    last_error = ""
    async with httpx.AsyncClient() as client:
        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "audio_url", "audio_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 400,
                "temperature": 0.1,
                "top_k": 1,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            try:
                response = await client.post(
                    f"{settings.NVIDIA_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=45.0,
                )
            except httpx.TimeoutException:
                last_error = f"timeout talking to {model}"
                continue
            except httpx.HTTPError as e:
                last_error = str(e)[:400]
                continue
            if response.status_code == 200:
                result = response.json()
                message = (result.get("choices") or [{}])[0].get("message") or {}
                content = message.get("content") or ""
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text") or "" for part in content if isinstance(part, dict)
                    )
                text = _transcript_text(str(content))
                if text:
                    return text
                last_error = "empty transcript"
                continue
            last_error = response.text[:400]
            if response.status_code == 401:
                break
    raise RuntimeError(last_error or "NVIDIA speech-to-text failed")


async def nemotron_chat(messages: list[dict[str, str]], max_tokens: int = 500) -> str:
    last_error = ""
    if settings.NVIDIA_API_KEY:
        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            for model in _nvidia_models():
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                }
                try:
                    response = await client.post(
                        f"{settings.NVIDIA_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=20.0,
                    )
                except httpx.TimeoutException:
                    last_error = f"timeout talking to {model}"
                    continue
                except httpx.HTTPError as e:
                    last_error = str(e)[:400]
                    continue
                if response.status_code == 200:
                    result = response.json()
                    content = (result.get("choices") or [{}])[0].get("message", {}).get("content") or ""
                    if content:
                        return content
                    last_error = "empty response"
                    continue
                last_error = response.text[:400]
                # A 401 means the key itself is bad; other models will not help.
                if response.status_code == 401:
                    break
                # 403 = this key cannot use that model. If Gemini is configured,
                # skip the remaining NVIDIA IDs instead of failing the whole chat.
                if response.status_code == 403 and (settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY):
                    break
    if last_error:
        tried = ", ".join(_nvidia_models())
        last_error = f"NVIDIA models unavailable ({tried}): {last_error}"
    if settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY:
        try:
            return await _gemini_complete(messages, max_tokens=max_tokens)
        except Exception as e:
            gemini_err = str(e)[:400]
            last_error = f"{last_error} | gemini: {gemini_err}" if last_error else gemini_err
    raise RuntimeError(last_error or "NVIDIA_API_KEY not configured")


VOICE_SYSTEM = (
    "You are JEEVAN, a calm nurse-style helper on a live voice call. "
    "Give short spoken remedies for small everyday issues: headache, mild fever, "
    "acidity, dehydration, sleep, cough, diet. Use 3-6 short sentences. "
    "You are not a doctor. If it sounds urgent or severe, tell them to tap Emergency SOS. "
    "Do not use markdown or lists with stars. Speak naturally."
)


async def _gemini_complete(messages: list[dict[str, str]], max_tokens: int = 500) -> str:
    key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for turn in messages:
        role = turn.get("role") or "user"
        text = turn.get("content") or ""
        if role == "system":
            system_parts.append(text)
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": text}],
            }
        )
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens},
    }
    if system_parts:
        payload["system_instruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
    models = [
        settings.GEMINI_MODEL or "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
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
            if response.status_code not in (404, 400, 403, 429):
                break
    raise RuntimeError(last_error or "Gemini chat failed")


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
    models = [model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
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
            if response.status_code not in (404, 400, 403, 429):
                break
    raise RuntimeError(last_error or "Gemini voice failed")


TAVUS_CONTEXT = (
    "You are JEEVAN, a live video-call health helper. You can hear the patient. "
    "This call is VOICE ONLY. The patient cannot type. Never ask them to type, "
    "write, fill a form, use a text box, or pick a date on a calendar. "
    "Never use canvas_show_input or canvas_show_calendar. "
    "Collect every detail out loud: full name, date of birth (day, month, year), "
    "then their small health issue. Wait for them to speak each answer. "
    "After you have name, date of birth, and the issue, you MUST show a Magic Canvas "
    "TEXT card with canvas_show_text. Title it 'Please verify'. Body must list "
    "Name, Date of birth, and Issue in short lines. Also speak the recap. "
    "Tell them the yellow verify card is on screen. Ask them to say 'yes that is correct' "
    "or speak any correction. They can also tap Looks correct on the card. "
    "Then give simple home remedies for small issues (headache, mild fever, acidity, "
    "dehydration, sleep, cough, diet). Speak in short sentences. You are not a doctor. "
    "If it sounds urgent, tell them to tap Emergency SOS."
)


def _tavus_context_for_user(user_id: str, patient_name: str | None) -> str:
    profile = get_health_profile(user_id)
    prior = list_chat(user_id, limit=16)
    chat_bits = "\n".join(
        f"{t.get('role')}: {t.get('content')}" for t in prior if t.get("content")
    )
    known = f"App already has display name {patient_name}." if patient_name else "Name is not on file."
    return (
        f"{TAVUS_CONTEXT}\n"
        "PRIVACY: This call is private to one signed-in patient. "
        "Do not recall, mention, or assume any other person's name, history, or previous call.\n"
        f"Patient record id: {user_id}. {known} Still ask them to SAY their full name and date of birth out loud.\n"
        f"Known allergies: {profile.get('allergies') or 'none noted'}.\n"
        f"Medicines: {profile.get('medicines') or 'none noted'}.\n"
        f"Conditions: {profile.get('conditions') or 'none noted'}.\n"
        f"Prior notes from THIS patient's app chat only:\n{chat_bits or '(none yet)'}"
    )


async def _ensure_voice_canvas(pal_id: str) -> None:
    """Disable typed Canvas fields so the PAL collects name/DOB by voice; keep the text recap card."""
    if not settings.TAVUS_API_KEY or not pal_id:
        return
    payload = {
        "config": {
            "usage_guidance": (
                "Never show input, calendar, or question cards. The patient answers by speaking. "
                "After you have spoken name, date of birth, and the health issue, show a text card "
                "titled Please verify listing those three facts. Then clear it when they confirm."
            ),
            "components": {
                "input": {"enabled": False},
                "calendar": {"enabled": False},
                "question": {"enabled": False},
                "scheduling_embed": {"enabled": False},
                "chart": {"enabled": False},
                "image": {"enabled": False},
            },
        }
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.put(
                f"https://tavusapi.com/v2/pals/{pal_id}/skills/magic_canvas",
                headers={"x-api-key": settings.TAVUS_API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=15.0,
            )
    except Exception:
        return


async def start_tavus_conversation(user_id: str, patient_name: str | None = None) -> dict[str, Any]:
    if not settings.TAVUS_API_KEY:
        raise RuntimeError("TAVUS_API_KEY not configured")

    replica = (settings.TAVUS_REPLICA_ID or "").strip() or None
    pal = (settings.TAVUS_PAL_ID or "").strip() or None
    persona = (settings.TAVUS_PERSONA_ID or "").strip() or None
    face = (settings.TAVUS_FACE_ID or "").strip() or None

    # Guard against the common mix-up: replica ids start with "r", persona ids with "p".
    # If a persona-shaped id lands in the replica slot, treat it as a persona so Tavus
    # doesn't reject it with "Invalid replica_uuid".
    if replica and replica.lower().startswith("p"):
        persona = persona or replica
        replica = None
    if face and face.lower().startswith("p"):
        face = None

    if not (replica or persona or pal):
        raise RuntimeError(
            "No Tavus replica/persona configured. Set TAVUS_PERSONA_ID (id starts with 'p') "
            "or TAVUS_REPLICA_ID (id starts with 'r') in .env."
        )

    await _ensure_voice_canvas(pal or persona or "")

    payload: dict[str, Any] = {
        "conversation_name": f"JEEVAN {user_id[:8]} {uuid.uuid4().hex[:8]}",
        "conversational_context": _tavus_context_for_user(user_id, patient_name),
        "custom_greeting": (
            f"Hello{(' ' + patient_name) if patient_name else ''}. I am Jeevan. "
            "This call is private and only about you. I can hear you, so please speak your answers. "
            "First say your full name, then your date of birth, then the small health issue. "
            "If it feels serious, use Emergency SOS in the app."
        ),
        # One memory bucket per signed-in patient. Omitting this (or sharing one tag)
        # makes Tavus recall other people's previous calls.
        "memory_stores": [f"jeevan-patient-{user_id}"],
    }
    if pal:
        payload["pal_id"] = pal
        if face or replica:
            payload["face_id"] = face or replica
    else:
        if persona:
            payload["persona_id"] = persona
        # Only send a replica_id when it's an actual replica; a persona can supply its
        # own default replica, and sending an invalid replica id breaks the call.
        if replica:
            payload["replica_id"] = replica
        elif face:
            payload["face_id"] = face
    callback = (settings.TAVUS_CALLBACK_URL or "").strip()
    if callback:
        payload["callback_url"] = callback
    last_error = ""
    data: dict[str, Any] = {}
    attempts = (payload, {k: v for k, v in payload.items() if k != "memory_stores"})
    async with httpx.AsyncClient() as client:
        for body in attempts:
            response = await client.post(
                "https://tavusapi.com/v2/conversations",
                headers={"x-api-key": settings.TAVUS_API_KEY, "Content-Type": "application/json"},
                json=body,
                timeout=30.0,
            )
            data = response.json() if response.content else {}
            if response.status_code < 400:
                last_error = ""
                break
            last_error = str(data.get("message") or data.get("error") or data)[:400]
            if "memory" not in last_error.lower():
                break
        else:
            raise RuntimeError(last_error or "Tavus conversation failed")
    url = data.get("conversation_url")
    cid = str(data.get("conversation_id") or "")
    if not url or not cid:
        raise RuntimeError(last_error or "Tavus did not return a conversation_url")
    _remember_tavus_owner(cid, user_id)
    return {
        "conversation_id": cid,
        "conversation_url": url,
        "status": data.get("status"),
    }


def ingest_tavus_transcript(conversation_id: str, transcript: list[Any], user_id: str | None = None) -> int:
    owner = _tavus_owner(conversation_id)
    uid = _uuid_or_none(user_id) or owner
    if not uid or not transcript:
        return 0
    if owner and uid != owner:
        return 0
    if not owner:
        # Unknown call — do not attach someone else's transcript to this account.
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


def _turns_as_text(turns: list[Any]) -> str:
    lines: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        role = (turn.get("role") or "user").lower()
        if role in ("replica", "model", "pal", "persona"):
            role = "assistant"
        content = (turn.get("content") or turn.get("text") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def empty_intake(conversation_id: str = "") -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "name": "",
        "date_of_birth": "",
        "issue": "",
        "recap": "",
        "confirmed": False,
    }


async def summarize_call_intake(conversation_id: str, turns: list[Any]) -> dict[str, Any]:
    intake = empty_intake(conversation_id)
    chat = _turns_as_text(turns)
    if not chat.strip():
        _call_intakes[conversation_id] = intake
        return intake
    try:
        raw = await nemotron_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract patient intake from a spoken video-call transcript. "
                        "Return JSON only with keys name, date_of_birth, issue, recap. "
                        "date_of_birth as spoken or YYYY-MM-DD if clear. recap is 2-4 short sentences. "
                        "Use empty strings when unknown. No markdown."
                    ),
                },
                {"role": "user", "content": chat[-6000:]},
            ],
            max_tokens=280,
        )
        parsed = _parse_json_object(raw)
        for key in ("name", "date_of_birth", "issue", "recap"):
            val = parsed.get(key)
            if isinstance(val, str):
                intake[key] = val.strip()
        if not intake["recap"]:
            intake["recap"] = chat[-800:]
    except Exception:
        intake["recap"] = chat[-800:]
    _call_intakes[conversation_id] = intake
    return intake


def get_call_intake(conversation_id: str) -> dict[str, Any]:
    return dict(_call_intakes.get(conversation_id) or empty_intake(conversation_id))


def confirm_call_intake(
    conversation_id: str,
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    owner = _tavus_owner(conversation_id)
    uid = _uuid_or_none(user_id)
    if owner and uid and owner != uid:
        raise RuntimeError("This video call belongs to another account")
    uid = owner or uid
    if not uid:
        raise RuntimeError("This video call is not linked to your account")
    current = get_call_intake(conversation_id)
    body = payload or {}
    for key in ("name", "date_of_birth", "issue", "recap"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            current[key] = val.strip()
    current["confirmed"] = True
    current["conversation_id"] = conversation_id
    _call_intakes[conversation_id] = current
    if uid:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        block = (
            f"Call intake {stamp}: Name: {current.get('name') or 'n/a'}; "
            f"DOB: {current.get('date_of_birth') or 'n/a'}; "
            f"Issue: {current.get('issue') or 'n/a'}."
        )
        profile = get_health_profile(uid)
        notes = (profile.get("notes") or "").strip()
        if "Call intake " in notes:
            kept = [ln for ln in notes.splitlines() if not ln.startswith("Call intake ")]
            notes = "\n".join(kept).strip()
        profile["notes"] = f"{block}\n{notes}".strip()
        save_health_profile(uid, profile)
        recap = current.get("recap") or block
        append_chat(uid, "assistant", f"Verified video-call intake: {recap}")
    return current


async def end_tavus_conversation(conversation_id: str, user_id: str | None = None) -> dict[str, Any]:
    if not settings.TAVUS_API_KEY or not conversation_id:
        return {"saved": 0, "intake": empty_intake(conversation_id)}
    owner = _tavus_owner(conversation_id)
    uid = _uuid_or_none(user_id)
    if owner and uid and owner != uid:
        raise RuntimeError("This video call belongs to another account")
    if not owner:
        return {"saved": 0, "intake": empty_intake(conversation_id)}
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://tavusapi.com/v2/conversations/{conversation_id}/end",
            headers={"x-api-key": settings.TAVUS_API_KEY},
            timeout=15.0,
        )
    saved = 0
    turns: list[Any] = []
    for delay in (2.0, 3.0, 5.0):
        await asyncio.sleep(delay)
        turns = await fetch_tavus_transcript(conversation_id)
        saved = ingest_tavus_transcript(conversation_id, turns, user_id=owner)
        if saved or turns:
            break
    intake = await summarize_call_intake(conversation_id, turns)
    return {"saved": saved, "conversation_id": conversation_id, "intake": intake}


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
