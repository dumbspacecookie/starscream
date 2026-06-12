"""Reverse geocoding via Nominatim (OpenStreetMap)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

_rate_lock = threading.Lock()
_last_request_at = 0.0


@dataclass(frozen=True)
class GeocodeResult:
    location_name: str | None
    country_code: str | None


def _wait_for_rate_limit(min_interval_s: float) -> None:
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_at
        if elapsed < min_interval_s:
            time.sleep(min_interval_s - elapsed)
        _last_request_at = time.monotonic()


def reverse_geocode(
    lat: float,
    lng: float,
    *,
    user_agent: str,
    rate_limit_s: float = 1.0,
    timeout_s: float = 10.0,
) -> GeocodeResult:
    """Reverse geocode coordinates; returns empty fields on failure."""
    _wait_for_rate_limit(rate_limit_s)
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={
                "lat": lat,
                "lon": lng,
                "format": "json",
                "addressdetails": 1,
                "zoom": 10,
            },
            headers={"User-Agent": user_agent},
            timeout=timeout_s,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("reverse geocode failed for (%s, %s): %s", lat, lng, exc)
        return GeocodeResult(location_name=None, country_code=None)

    address = data.get("address") or {}
    country_code = address.get("country_code")
    if country_code:
        country_code = country_code.upper()

    location_name = data.get("display_name")
    if not location_name:
        parts = [
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("hamlet"),
            address.get("state") or address.get("region"),
            address.get("country"),
        ]
        location_name = ", ".join(p for p in parts if p) or None

    return GeocodeResult(location_name=location_name, country_code=country_code)
