"""Forward / reverse geocode for staff pickup pinning."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from app.core.config import settings

_UA = {"User-Agent": "JEEVAN-dispatch/1.0 (emergency-prototype)"}


def _tomtom_key() -> str:
    return (settings.TOMTOM_API_KEY or "").strip()


def geocode_query(query: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    if not q:
        return None
    key = _tomtom_key()
    if key:
        url = f"https://api.tomtom.com/search/2/geocode/{quote(q)}.json?key={key}&limit=1"
        try:
            data = requests.get(url, timeout=8).json()
            results = data.get("results") or []
            if results:
                pos = results[0].get("position") or {}
                addr = (results[0].get("address") or {}).get("freeformAddress") or q
                lat, lng = pos.get("lat"), pos.get("lon")
                if lat is not None and lng is not None:
                    return {"lat": float(lat), "lng": float(lng), "address": addr, "source": "tomtom"}
        except Exception as exc:
            print("TomTom geocode failed:", exc)
    url = "https://nominatim.openstreetmap.org/search"
    try:
        data = requests.get(
            url,
            params={"q": q, "format": "json", "limit": 1},
            headers=_UA,
            timeout=8,
        ).json()
        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lng": float(data[0]["lon"]),
                "address": data[0].get("display_name") or q,
                "source": "nominatim",
            }
    except Exception as exc:
        print("Nominatim geocode failed:", exc)
    return None


def reverse_geocode(lat: float, lng: float) -> dict[str, Any] | None:
    key = _tomtom_key()
    if key:
        url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lng}.json?key={key}"
        try:
            data = requests.get(url, timeout=8).json()
            addrs = data.get("addresses") or []
            if addrs:
                addr = (addrs[0].get("address") or {}).get("freeformAddress")
                if addr:
                    return {"lat": lat, "lng": lng, "address": addr, "source": "tomtom"}
        except Exception as exc:
            print("TomTom reverse geocode failed:", exc)
    try:
        data = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "json"},
            headers=_UA,
            timeout=8,
        ).json()
        addr = data.get("display_name")
        if addr:
            return {"lat": lat, "lng": lng, "address": addr, "source": "nominatim"}
    except Exception as exc:
        print("Nominatim reverse geocode failed:", exc)
    return {"lat": lat, "lng": lng, "address": f"{lat:.5f}, {lng:.5f}", "source": "coords"}
