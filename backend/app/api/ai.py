from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
import httpx
import base64
from typing import Any, Optional
from app.core.config import settings
from app.core.security import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatBody(BaseModel):
    message: str
    history: list[dict[str, str]] = []


@router.post("/chat")
async def chat(body: ChatBody, _user: dict[str, Any] = Depends(get_current_user)):
    if not settings.NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured in .env")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")

    messages = [
        {
            "role": "system",
            "content": (
                "You are JEEVAN, an emergency first-aid assistant for patients in Bengaluru. "
                "Give short, calm, practical steps. You are not a doctor. "
                "If symptoms sound life-threatening, tell them to stay on the line and request an ambulance in the app."
            ),
        }
    ]
    for turn in body.history[-8:]:
        role = turn.get("role") if turn.get("role") in ("user", "assistant") else "user"
        messages.append({"role": role, "content": turn.get("content") or ""})
    messages.append({"role": "user", "content": body.message.strip()})

    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.NVIDIA_MODEL,
        "messages": messages,
        "max_tokens": 400,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=45.0,
            )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="AI provider error")
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return {"status": "success", "reply": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-report")
async def analyze_report(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
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
                # Read image
                contents = await image.read()
                base64_img = base64.b64encode(contents).decode("utf-8")
                mime_type = image.content_type or "image/jpeg"
                data_url = f"data:{mime_type};base64,{base64_img}"

                # Only include data URL, as text might not be used here or we append it
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
