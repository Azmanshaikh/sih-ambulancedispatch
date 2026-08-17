from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
import httpx
import base64
from typing import Any, Optional
from app.core.config import settings
from app.core.security import get_current_user, require_roles
from app.services.patient_care import (
    append_chat,
    confirm_call_intake,
    end_tavus_conversation,
    ingest_tavus_transcript,
    list_chat,
    nemotron_chat,
    start_tavus_conversation,
)

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatBody(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class IntakeConfirmBody(BaseModel):
    name: str = ""
    date_of_birth: str = ""
    issue: str = ""
    recap: str = ""


@router.get("/chat/history")
async def chat_history(user: dict[str, Any] = Depends(require_roles("patient"))):
    return {"status": "success", "messages": list_chat(user["id"])}


@router.post("/chat")
async def chat(body: ChatBody, user: dict[str, Any] = Depends(require_roles("patient"))):
    if not settings.NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured in .env")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")

    stored = list_chat(user["id"], limit=16)
    messages = [
        {
            "role": "system",
            "content": (
                "You are JEEVAN, a calm everyday health assistant for patients. "
                "Help with common issues (fever, headache, diet, rest). You are not a doctor. "
                "If symptoms sound life-threatening, tell them to tap Emergency SOS in the app. "
                "Keep replies short."
            ),
        }
    ]
    source = stored or body.history[-8:]
    for turn in source[-8:]:
        role = turn.get("role") if turn.get("role") in ("user", "assistant") else "user"
        messages.append({"role": role, "content": turn.get("content") or ""})
    messages.append({"role": "user", "content": body.message.strip()})

    try:
        content = await nemotron_chat(messages, max_tokens=400)
    except Exception as e:
        raw = str(e)
        low = raw.lower()
        if "unauthorized" in low or "authentication" in low or "401" in low or "invalid api key" in low:
            raise HTTPException(
                status_code=502,
                detail="AI chat is unavailable: the NVIDIA API key is invalid or expired. Update NVIDIA_API_KEY.",
            )
        if "forbidden" in low or "403" in low or "not found for account" in low:
            raise HTTPException(
                status_code=502,
                detail="AI chat is unavailable: your NVIDIA key can't access the configured models. Set NVIDIA_MODEL to a model you have access to (e.g. nvidia/nemotron-mini-4b-instruct).",
            )
        raise HTTPException(status_code=502, detail=raw[:300])
    if not content:
        raise HTTPException(status_code=502, detail="AI provider error")
    append_chat(user["id"], "user", body.message.strip())
    append_chat(user["id"], "assistant", content)
    return {"status": "success", "reply": content}


@router.post("/tavus/start")
async def tavus_start(user: dict[str, Any] = Depends(require_roles("patient"))):
    try:
        data = await start_tavus_conversation(
            user["id"],
            (user.get("profile") or {}).get("full_name") or user.get("email"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400])
    return {"status": "success", **data}


@router.post("/tavus/{conversation_id}/end")
async def tavus_end(conversation_id: str, _user: dict[str, Any] = Depends(require_roles("patient"))):
    result = await end_tavus_conversation(conversation_id)
    return {"status": "success", **result}


@router.post("/tavus/{conversation_id}/confirm")
async def tavus_confirm(
    conversation_id: str,
    body: IntakeConfirmBody,
    _user: dict[str, Any] = Depends(require_roles("patient")),
):
    intake = confirm_call_intake(conversation_id, body.model_dump())
    return {"status": "success", "intake": intake}


@router.post("/tavus/webhook")
async def tavus_webhook(payload: dict[str, Any]):
    event = payload.get("event_type") or ""
    cid = str(payload.get("conversation_id") or "")
    if event == "application.transcription_ready" and cid:
        props = payload.get("properties") or payload
        transcript = props.get("transcript") or []
        saved = ingest_tavus_transcript(cid, transcript)
        return {"status": "success", "saved": saved}
    return {"status": "ignored"}


@router.post("/analyze-report")
async def analyze_report(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    _user: dict[str, Any] = Depends(get_current_user),
):
    if not settings.NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured in .env")

    if not text and not image:
        raise HTTPException(status_code=400, detail="Must provide either text or image")

    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            if image:
                contents = await image.read()
                base64_img = base64.b64encode(contents).decode("utf-8")
                mime_type = image.content_type or "image/jpeg"
                data_url = f"data:{mime_type};base64,{base64_img}"

                prompt_text = "Analyze this medical report and provide a concise assessment including: severity (Low, Medium, High, Critical), summary of findings, recommended action, and any vitals detected. Format as structured text."
                if text:
                    prompt_text += f"\nAdditional context from user: {text}"

                payload = {
                    "model": settings.NVIDIA_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": data_url}}
                            ]
                        }
                    ],
                    "max_tokens": 1024,
                }
            else:
                prompt_text = f"Analyze this medical report and provide a concise assessment including: severity (Low, Medium, High, Critical), summary of findings, recommended action, and any vitals detected. Format as structured text.\n\nReport:\n{text}"
                payload = {
                    "model": settings.NVIDIA_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt_text}
                    ],
                    "max_tokens": 1024,
                }

            response = await client.post(
                f"{settings.NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )

            if response.status_code != 200:
                print("NVIDIA API Error:", response.text)
                raise HTTPException(status_code=502, detail=f"AI Provider error: {response.text}")

            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                return {"status": "success", "analysis": content}
            else:
                return {"status": "error", "message": "Unexpected response from AI provider"}

    except Exception as e:
        print("Analyze report exception:", e)
        raise HTTPException(status_code=500, detail=str(e))
