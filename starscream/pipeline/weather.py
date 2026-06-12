"""Historical weather lookup via Open-Meteo (free, no API key)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# WMO weather interpretation codes (Open-Meteo uses these).
_WMO_SUMMARY: dict[int, str] = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


@dataclass(frozen=True)
class WeatherResult:
    weather: str | None
    temperature_c: float | None


def _weather_summary(code: int | None) -> str | None:
    if code is None:
        return None
    return _WMO_SUMMARY.get(code, "unknown")


def lookup_weather(
    lat: float,
    lng: float,
    recorded_at: datetime,
    *,
    timeout_s: float = 15.0,
) -> WeatherResult:
    """Fetch hourly weather for the recording date; returns empty on failure."""
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    else:
        recorded_at = recorded_at.astimezone(timezone.utc)

    date_str = recorded_at.date().isoformat()
    hour = recorded_at.hour

    try:
        response = httpx.get(
            ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "start_date": date_str,
                "end_date": date_str,
                "hourly": "temperature_2m,weather_code",
                "timezone": "UTC",
            },
            timeout=timeout_s,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("weather lookup failed for (%s, %s) on %s: %s", lat, lng, date_str, exc)
        return WeatherResult(weather=None, temperature_c=None)

    hourly = data.get("hourly") or {}
    times: list[str] = hourly.get("time") or []
    temperatures: list[float | None] = hourly.get("temperature_2m") or []
    codes: list[int | None] = hourly.get("weather_code") or []

    if not times:
        return WeatherResult(weather=None, temperature_c=None)

    target_prefix = f"{date_str}T{hour:02d}:"
    idx = next((i for i, t in enumerate(times) if t.startswith(target_prefix)), None)
    if idx is None:
        idx = min(hour, len(times) - 1)

    temp = temperatures[idx] if idx < len(temperatures) else None
    code = codes[idx] if idx < len(codes) else None

    return WeatherResult(
        weather=_weather_summary(code),
        temperature_c=float(temp) if temp is not None else None,
    )
