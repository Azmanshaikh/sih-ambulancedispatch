from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
import httpx
import base64
from typing import Optional
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI"])

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
