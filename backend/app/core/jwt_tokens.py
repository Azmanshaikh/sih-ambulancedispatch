from __future__ import annotations

from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


def _issuer() -> str:
    raw = (settings.SUPABASE_JWT_ISSUER or "").strip()
    if raw:
        return raw.rstrip("/")
    url = (settings.SUPABASE_URL or settings.VITE_SUPABASE_URL or "").strip().rstrip("/")
    return f"{url}/auth/v1" if url else ""


def decode_supabase_access_token(token: str) -> dict[str, Any] | None:
    """Verify a Supabase access JWT locally. Returns a normalized user dict or None."""
    secret = (settings.SUPABASE_JWT_SECRET or "").strip()
    if not secret or not token:
        return None

    audience = (settings.SUPABASE_JWT_AUDIENCE or "authenticated").strip() or "authenticated"
    issuer = _issuer()
    options = {
        "require": ["exp", "sub"],
        "verify_aud": True,
        "verify_iss": bool(issuer),
        "verify_exp": True,
        "verify_signature": True,
    }
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            issuer=issuer or None,
            options=options,
        )
    except InvalidTokenError:
        return None

    if claims.get("role") not in ("authenticated",):
        return None

    user_id = claims.get("sub")
    meta = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    email = claims.get("email") or meta.get("email")
    if not user_id or not email:
        return None
    return {
        "id": str(user_id),
        "email": str(email),
        "user_metadata": meta,
    }
