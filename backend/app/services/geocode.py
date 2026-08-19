"""Forward / reverse geocode for staff pickup pinning.

TomTom (if keyed) → Photon → Nominatim. Photon is the cloud-friendly fallback
because Nominatim often blocks datacenter IPs such as Render.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from app.core.config import settings

_UA = {"User-Agent": "JEEVAN-dispatch/1.0 (emergency-prototype; https://github.com/sih-ambulancedispatch)"}
_BIAS_LAT = 13.1344
_BIAS_LNG = 77.5693


def _tomtom_key() -> str:
    return (settings.TOMTOM_API_KEY or "").strip()


def _photon_address(props: dict[str, Any], fallback: str) -> str:
    parts = [
        props.get("name"),
        " ".join(p for p in (props.get("housenumber"), props.get("street")) if p),
        props.get("locality") or props.get("city") or props.get("district"),
        props.get("county") or props.get("state"),
        props.get("postcode"),
        props.get("country"),
    ]
    text = ", ".join(dict.fromkeys(p for p in parts if p))
    return text or fallback


def _photon_search(query: str) -> dict[str, Any] | None:
    url = (
        "https://photon.komoot.io/api/"
        f"?q={quote(query)}&limit=1&lat={_BIAS_LAT}&lon={_BIAS_LNG}"
    )
    try:
        resp = requests.get(url, timeout=8, headers=_UA)
        if resp.status_code != 200:
            print("Photon geocode HTTP", resp.status_code)
            return None
        feats = (resp.json() or {}).get("features") or []
        if not feats:
            return None
        feat = feats[0]
        lng, lat = feat["geometry"]["coordinates"]
        addr = _photon_address(feat.get("properties") or {}, query)
        return {"lat": float(lat), "lng": float(lng), "address": addr, "source": "photon"}
    except Exception as exc:
        print("Photon geocode failed:", exc)
        return None


def _photon_reverse(lat: float, lng: float) -> dict[str, Any] | None:
    url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lng}"
    try:
        resp = requests.get(url, timeout=8, headers=_UA)
        if resp.status_code != 200:
            print("Photon reverse HTTP", resp.status_code)
            return None
        feats = (resp.json() or {}).get("features") or []
        if not feats:
            return None
        addr = _photon_address(feats[0].get("properties") or {}, f"{lat:.5f}, {lng:.5f}")
        return {"lat": lat, "lng": lng, "address": addr, "source": "photon"}
    except Exception as exc:
        print("Photon reverse failed:", exc)
        return None


def geocode_query(query: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    if not q:
        return None
    key = _tomtom_key()
    if key:
        url = f"https://api.tomtom.com/search/2/geocode/{quote(q)}.json?key={key}&limit=1"
        url += f"&lat={_BIAS_LAT}&lon={_BIAS_LNG}"
        try:
            resp = requests.get(url, timeout=8)
            data = resp.json() if resp.ok else {}
            results = data.get("results") or []
            if results:
                pos = results[0].get("position") or {}
                addr = (results[0].get("address") or {}).get("freeformAddress") or q
                lat, lng = pos.get("lat"), pos.get("lon")
                if lat is not None and lng is not None:
                    return {"lat": float(lat), "lng": float(lng), "address": addr, "source": "tomtom"}
        except Exception as exc:
            print("TomTom geocode failed:", exc)

    hit = _photon_search(q)
    if hit:
        return hit

    url = "https://nominatim.openstreetmap.org/search"
    try:
        resp = requests.get(
            url,
            params={"q": q, "format": "json", "limit": 1},
            headers=_UA,
            timeout=8,
        )
        if resp.ok:
            data = resp.json()
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]),
                    "address": data[0].get("display_name") or q,
                    "source": "nominatim",
                }
        else:
            print("Nominatim geocode HTTP", resp.status_code)
    except Exception as exc:
        print("Nominatim geocode failed:", exc)
    return None


def reverse_geocode(lat: float, lng: float) -> dict[str, Any] | None:
    key = _tomtom_key()
    if key:
        url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lng}.json?key={key}"
        try:
            resp = requests.get(url, timeout=8)
            data = resp.json() if resp.ok else {}
            addrs = data.get("addresses") or []
            if addrs:
                addr = (addrs[0].get("address") or {}).get("freeformAddress")
                if addr:
                    return {"lat": lat, "lng": lng, "address": addr, "source": "tomtom"}
        except Exception as exc:
            print("TomTom reverse geocode failed:", exc)

    hit = _photon_reverse(lat, lng)
    if hit:
        return hit

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "json"},
            headers=_UA,
            timeout=8,
        )
        if resp.ok:
            data = resp.json()
            addr = data.get("display_name")
            if addr:
                return {"lat": lat, "lng": lng, "address": addr, "source": "nominatim"}
        else:
            print("Nominatim reverse HTTP", resp.status_code)
    except Exception as exc:
        print("Nominatim reverse geocode failed:", exc)
    return {"lat": lat, "lng": lng, "address": f"{lat:.5f}, {lng:.5f}", "source": "coords"}
