from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

supabase_client = None

try:
    from supabase import create_client

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
except Exception as e:
    logger.warning("Supabase Python SDK unavailable (%s); using REST fallback.", e)
    supabase_client = None


def _rest_headers(prefer: str | None = None) -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY or ""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def auth_user_from_token(access_token: str) -> dict[str, Any] | None:
    from app.core.jwt_tokens import decode_supabase_access_token

    local = decode_supabase_access_token(access_token)
    if local:
        return local
    if (settings.SUPABASE_JWT_SECRET or "").strip():
        return None
    if not settings.SUPABASE_URL:
        return None
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    key = settings.SUPABASE_ANON_KEY or settings.VITE_SUPABASE_ANON_KEY or ""
    try:
        res = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}", "apikey": key},
            timeout=8,
        )
        if res.status_code != 200:
            return None
        return res.json()
    except Exception:
        logger.error("auth user lookup failed")
        return None


def rest_select(table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if not settings.SUPABASE_URL or not (settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY):
        return []
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    try:
        res = requests.get(url, headers=_rest_headers(), params=params or {}, timeout=8)
        if res.status_code >= 400:
            logger.warning("REST select %s failed: %s", table, res.status_code)
            return []
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error("REST select failed: %s", e)
        return []


def rest_upsert(table: str, row: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return None
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}?on_conflict=id"
    try:
        res = requests.post(
            url,
            headers=_rest_headers("resolution=merge-duplicates,return=representation"),
            json=row,
            timeout=8,
        )
        if res.status_code >= 400:
            logger.warning("REST upsert %s failed: %s", table, res.status_code)
            return None
        data = res.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.error("REST upsert failed: %s", e)
    return None


def rest_insert(table: str, row: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return None
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    try:
        res = requests.post(
            url,
            headers=_rest_headers("return=representation"),
            json=row,
            timeout=8,
        )
        if res.status_code >= 400:
            logger.warning("REST insert %s failed: %s", table, res.status_code)
            return None
        data = res.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.error("REST insert failed: %s", e)
    return None


def rest_update(table: str, match: dict[str, str], row: dict[str, Any]) -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    try:
        res = requests.patch(url, headers=_rest_headers(), params=match, json=row, timeout=8)
        if res.status_code >= 400:
            logger.warning("REST update %s failed: %s", table, res.status_code)
    except Exception as e:
        logger.error("REST update failed: %s", e)
