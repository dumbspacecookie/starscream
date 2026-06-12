from dataclasses import dataclass
from datetime import datetime

from starscream.config import Settings, get_settings
from starscream.db.models import Season
from starscream.pipeline.cross_modal import enrich_cross_modal
from starscream.pipeline.geocode import reverse_geocode
from starscream.pipeline.habitat import lookup_habitat
from starscream.pipeline.metrics import record_enrichment_failure
from starscream.pipeline.weather import lookup_weather


@dataclass
class Enrichment:
    season: Season | None
    location_name: str | None
    country_code: str | None
    habitat: str | None
    weather: str | None
    temperature_c: float | None
    cross_modal_links: dict | None = None


def _derive_season(recorded_at: datetime, lat: float) -> Season:
    month = recorded_at.month
    northern = lat >= 0
    if northern:
        if month in (3, 4, 5):
            return Season.SPRING
        if month in (6, 7, 8):
            return Season.SUMMER
        if month in (9, 10, 11):
            return Season.AUTUMN
        return Season.WINTER
    # Southern hemisphere — inverted
    if month in (3, 4, 5):
        return Season.AUTUMN
    if month in (6, 7, 8):
        return Season.WINTER
    if month in (9, 10, 11):
        return Season.SPRING
    return Season.SUMMER


def enrich_metadata(
    *,
    lat: float,
    lng: float,
    recorded_at: datetime,
    location_name: str | None,
    country_code: str | None,
    settings: Settings | None = None,
) -> Enrichment:
    """Best-effort enrichment: geocode, habitat, weather, season."""
    cfg = settings or get_settings()

    resolved_name = location_name
    resolved_country = country_code

    if cfg.enrich_geocode and (not resolved_name or not resolved_country):
        try:
            geocode = reverse_geocode(
                lat,
                lng,
                user_agent=cfg.nominatim_user_agent,
                rate_limit_s=cfg.nominatim_rate_limit_s,
            )
            if not resolved_name:
                resolved_name = geocode.location_name
            if not resolved_country:
                resolved_country = geocode.country_code
        except Exception as exc:
            record_enrichment_failure("geocode", exc)

    habitat = None
    if cfg.enrich_habitat:
        try:
            habitat = lookup_habitat(lat, lng)
        except Exception as exc:
            record_enrichment_failure("habitat", exc)

    weather = None
    temperature_c = None
    if cfg.enrich_weather:
        try:
            wx = lookup_weather(lat, lng, recorded_at)
            weather = wx.weather
            temperature_c = wx.temperature_c
        except Exception as exc:
            record_enrichment_failure("weather", exc)

    cross_modal_links = None
    if cfg.enrich_osm:
        try:
            cross_modal_links = enrich_cross_modal(lat, lng, settings=cfg)
        except Exception as exc:
            record_enrichment_failure("osm", exc)

    return Enrichment(
        season=_derive_season(recorded_at, lat),
        location_name=resolved_name,
        country_code=resolved_country,
        habitat=habitat,
        weather=weather,
        temperature_c=temperature_c,
        cross_modal_links=cross_modal_links,
    )
