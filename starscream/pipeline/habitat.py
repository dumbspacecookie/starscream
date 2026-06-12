"""Coarse habitat / biome lookup from coordinates (v1 heuristic)."""

from __future__ import annotations

# IUCN-inspired habitat codes aligned with WWF terrestrial biomes (simplified).
_RAINFOREST_BOXES: list[tuple[float, float, float, float]] = [
    # Amazon basin
    (-75.0, -20.0, -45.0, 5.0),
    # Congo basin
    (10.0, -5.0, 30.0, 5.0),
    # Southeast Asia / Malesia
    (95.0, -10.0, 140.0, 10.0),
    # Central America / Caribbean lowlands
    (-92.0, 8.0, -75.0, 18.0),
]

_DESERT_BOXES: list[tuple[float, float, float, float]] = [
    # Sahara
    (-15.0, 15.0, 35.0, 32.0),
    # Arabian
    (35.0, 12.0, 60.0, 32.0),
    # Australian interior
    (115.0, -32.0, 145.0, -18.0),
    # SW North America
    (-120.0, 25.0, -100.0, 38.0),
    # Atacama / coastal Peru-Chile
    (-75.0, -28.0, -68.0, -15.0),
]

_MEDITERRANEAN_BOXES: list[tuple[float, float, float, float]] = [
    (-10.0, 30.0, 40.0, 45.0),
    (-125.0, 30.0, -115.0, 42.0),
    (115.0, -35.0, 140.0, -30.0),
]


def _in_box(lng: float, lat: float, west: float, south: float, east: float, north: float) -> bool:
    return west <= lng <= east and south <= lat <= north


def _in_any_box(
    lat: float,
    lng: float,
    boxes: list[tuple[float, float, float, float]],
) -> bool:
    return any(_in_box(lng, lat, *box) for box in boxes)


def lookup_habitat(lat: float, lng: float) -> str:
    """Return a coarse IUCN-style habitat code from lat/lng."""
    abs_lat = abs(lat)

    if abs_lat >= 66.5:
        return "polar_tundra"
    if abs_lat >= 55.0:
        return "boreal_forest"
    if abs_lat >= 45.0:
        return "temperate_forest"
    if abs_lat >= 35.0:
        if _in_any_box(lat, lng, _MEDITERRANEAN_BOXES):
            return "mediterranean"
        if _in_any_box(lat, lng, _DESERT_BOXES):
            return "desert"
        return "temperate_grassland"
    if abs_lat >= 23.5:
        if _in_any_box(lat, lng, _DESERT_BOXES):
            return "desert"
        if _in_any_box(lat, lng, _MEDITERRANEAN_BOXES):
            return "mediterranean"
        return "subtropical_forest"

    # Tropics
    if _in_any_box(lat, lng, _RAINFOREST_BOXES):
        return "tropical_rainforest"
    if _in_any_box(lat, lng, _DESERT_BOXES):
        return "desert"
    if abs(lng) > 160 or (120 <= lng <= 180):
        return "tropical_rainforest"
    return "tropical_savanna"
