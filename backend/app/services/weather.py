"""Current precipitation at a lat/lng via Open-Meteo (no API key required)."""

from __future__ import annotations

import time
from typing import Any

import requests

_UA = {"User-Agent": "JEEVAN-dispatch/1.0 (emergency-prototype; https://github.com/sih-ambulancedispatch)"}
_CACHE_TTL_SEC = 600
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}

# WMO weather codes for drizzle, rain, showers, and thunderstorms.
_RAIN_CODES = frozenset(
    {
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        61,
        63,
        65,
        66,
        67,
        80,
        81,
        82,
        95,
        96,
        99,
    }
)


def _cache_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, 3), round(lng, 3))


def _fetch_current(lat: float, lng: float) -> dict[str, Any] | None:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        "&current=precipitation,rain,weather_code"
        "&timezone=Asia%2FKolkata"
    )
    try:
        resp = requests.get(url, timeout=8, headers=_UA)
        if resp.status_code != 200:
            print("Open-Meteo HTTP", resp.status_code)
            return None
        return (resp.json() or {}).get("current") or {}
    except Exception as exc:
        print("Open-Meteo weather failed:", exc)
        return None


def _rain_from_current(current: dict[str, Any]) -> bool:
    precip = float(current.get("precipitation") or 0)
    rain = float(current.get("rain") or 0)
    code = int(current.get("weather_code") or 0)
    return precip > 0 or rain > 0 or code in _RAIN_CODES


def weather_snapshot(lat: float, lng: float) -> dict[str, Any]:
    """Return current precipitation snapshot and rain flag for a location."""
    key = _cache_key(lat, lng)
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    current = _fetch_current(lat, lng) or {}
    snap = {
        "lat": lat,
        "lng": lng,
        "is_raining": _rain_from_current(current) if current else False,
        "precipitation_mm": float(current.get("precipitation") or 0) if current else None,
        "rain_mm": float(current.get("rain") or 0) if current else None,
        "weather_code": int(current.get("weather_code") or 0) if current else None,
        "observed_at": current.get("time"),
        "source": "open-meteo",
    }
    _cache[key] = (now, snap)
    return snap


def is_raining_at(lat: float, lng: float) -> bool:
    return bool(weather_snapshot(lat, lng).get("is_raining"))
