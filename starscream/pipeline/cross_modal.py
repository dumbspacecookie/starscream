"""Cross-modal enrichment via OpenStreetMap (Overpass API)."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from starscream.config import Settings, get_settings

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

MEANINGFUL_TYPES = ("building", "highway", "natural", "amenity")


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _feature_type(tags: dict[str, Any]) -> str | None:
    if tags.get("building"):
        return "building"
    if tags.get("highway"):
        return "highway"
    if tags.get("natural"):
        return "natural"
    if tags.get("amenity"):
        return "amenity"
    return None


def _feature_name(tags: dict[str, Any], feature_type: str) -> str | None:
    for key in ("name", feature_type, "building", "highway", "natural", "amenity"):
        value = tags.get(key)
        if value and value != "yes":
            return str(value)
    return None


def _element_coords(element: dict[str, Any]) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if center and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _parse_overpass_elements(
    elements: list[dict[str, Any]], lat: float, lng: float
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for element in elements:
        tags = element.get("tags") or {}
        feature_type = _feature_type(tags)
        if not feature_type:
            continue
        coords = _element_coords(element)
        if not coords:
            continue
        elat, elng = coords
        features.append(
            {
                "type": feature_type,
                "name": _feature_name(tags, feature_type),
                "osm_id": element.get("id"),
                "distance_m": round(_haversine_m(lat, lng, elat, elng), 1),
            }
        )
    features.sort(key=lambda f: f["distance_m"])
    return features


def fetch_osm_features(
    lat: float,
    lng: float,
    radius_m: float = 100,
    *,
    timeout_s: float = 25.0,
) -> list[dict[str, Any]]:
    """Fetch nearby OSM features within radius via Overpass API."""
    query = f"""
[out:json][timeout:25];
(
  nwr(around:{radius_m},{lat},{lng})["building"];
  nwr(around:{radius_m},{lat},{lng})["highway"];
  nwr(around:{radius_m},{lat},{lng})["natural"];
  nwr(around:{radius_m},{lat},{lng})["amenity"];
);
out center tags;
""".strip()
    try:
        response = httpx.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=timeout_s,
            headers={"User-Agent": get_settings().nominatim_user_agent},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("OSM Overpass lookup failed for (%s, %s): %s", lat, lng, exc)
        return []

    return _parse_overpass_elements(data.get("elements") or [], lat, lng)


def pick_primary_feature(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the closest meaningful OSM feature, if any."""
    meaningful = [f for f in features if f.get("type") in MEANINGFUL_TYPES]
    if not meaningful:
        return None
    return min(meaningful, key=lambda f: f["distance_m"])


def enrich_cross_modal(
    lat: float,
    lng: float,
    *,
    radius_m: float = 100,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Build cross_modal_links payload for a recording location."""
    _ = settings  # reserved for future rate-limit / toggle overrides
    features = fetch_osm_features(lat, lng, radius_m=radius_m)
    primary = pick_primary_feature(features)
    result: dict[str, Any] = {
        "nearby_features": features,
        "osm_primary_type": primary["type"] if primary else None,
        "osm_primary_name": primary["name"] if primary else None,
        "osm_primary_id": primary["osm_id"] if primary else None,
        "osm_primary_distance_m": primary["distance_m"] if primary else None,
    }
    if primary:
        result["primary"] = primary
    return result
