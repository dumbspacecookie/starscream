"""iNaturalist federation connector.

Harvests research-grade observations with sounds via API v1.
Species → source_object, observation geo → lat/lng, CC-BY/CC0 only.

API docs: https://api.inaturalist.org/v1/docs/
"""

from datetime import datetime, timezone

import httpx

from starscream.federation.base import FederatedRecord, FederationConnector

API_BASE = "https://api.inaturalist.org/v1/observations"

LICENSE_MAP = {
    "cc0": "CC0",
    "cc-by": "CC-BY",
    "cc-by-sa": "CC-BY",
    "cc-by-nc": "CC-BY-NC",
}

ICONIC_TAXONOMY = {
    "aves": "WILDLIFE.BIRD",
    "mammalia": "WILDLIFE.MAMMAL",
    "insecta": "WILDLIFE.INSECT",
    "reptilia": "WILDLIFE.MAMMAL",
    "amphibia": "WILDLIFE.MAMMAL",
    "actinopterygii": "WILDLIFE.MAMMAL",
    "animalia": "WILDLIFE",
    "plantae": "NATURAL.FOREST",
    "fungi": "NATURAL.FOREST",
}


def map_license(license_code: str | None) -> str | None:
    if not license_code:
        return None
    return LICENSE_MAP.get(license_code.lower().replace("_", "-"))


def map_taxonomy(taxon: dict | None) -> str:
    if not taxon:
        return "WILDLIFE"
    iconic = (taxon.get("iconic_taxon_name") or "").lower()
    if iconic in ICONIC_TAXONOMY:
        return ICONIC_TAXONOMY[iconic]
    name = (taxon.get("name") or "").lower()
    if "aves" in name or "bird" in name:
        return "WILDLIFE.BIRD"
    if "mammal" in name:
        return "WILDLIFE.MAMMAL"
    if "insect" in name:
        return "WILDLIFE.INSECT"
    return "WILDLIFE"


def _parse_coords(obs: dict) -> tuple[float, float]:
    geojson = obs.get("geojson") or {}
    if geojson.get("type") == "Point" and geojson.get("coordinates"):
        lng, lat = geojson["coordinates"][:2]
        return float(lat), float(lng)

    location = obs.get("location") or ""
    if location and "," in location:
        try:
            lat_s, lng_s = location.split(",", 1)
            return float(lat_s.strip()), float(lng_s.strip())
        except ValueError:
            pass
    return 0.0, 0.0


def _parse_recorded_at(obs: dict) -> datetime:
    for key in ("time_observed_at", "observed_on_details", "observed_on"):
        raw = obs.get(key)
        if not raw:
            continue
        try:
            if isinstance(raw, str):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _species_label(taxon: dict | None, obs_id: int) -> str:
    if not taxon:
        return f"inaturalist-obs-{obs_id}"
    common = (taxon.get("preferred_common_name") or "").strip()
    if common:
        return common
    name = (taxon.get("name") or "").strip()
    return name or f"inaturalist-obs-{obs_id}"


def _pick_sound(sounds: list[dict]) -> dict | None:
    for sound in sounds:
        if map_license(sound.get("license_code")):
            return sound
    return None


def parse_observation(data: dict) -> FederatedRecord | None:
    sounds = data.get("sounds") or []
    sound = _pick_sound(sounds)
    if not sound:
        return None

    license_code = map_license(sound.get("license_code"))
    if not license_code:
        return None

    obs_id = data["id"]
    taxon = data.get("taxon") or {}
    lat, lng = _parse_coords(data)
    species = _species_label(taxon, obs_id)
    tags = []
    if taxon.get("name"):
        tags.append(taxon["name"].lower().replace(" ", "_"))
    if taxon.get("preferred_common_name"):
        tags.append(taxon["preferred_common_name"].lower().replace(" ", "_"))

    return FederatedRecord(
        external_id=str(obs_id),
        external_url=f"https://www.inaturalist.org/observations/{obs_id}",
        taxonomy_code=map_taxonomy(taxon),
        lat=lat,
        lng=lng,
        recorded_at=_parse_recorded_at(data),
        license=license_code,
        title=f"{species} — iNaturalist #{obs_id}",
        description=data.get("description") or None,
        tags=tags,
        location_name=data.get("place_guess"),
        country_code=None,
        duration_s=None,
        preview_url=sound.get("file_url") or sound.get("url"),
        source_object=species,
        source_action="vocalization",
        username=(data.get("user") or {}).get("login"),
    )


class INaturalistConnector(FederationConnector):
    slug = "inaturalist"

    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        # has_sounds=true returns empty sounds[] — sound_license embeds sound metadata.
        params = {
            "quality_grade": "research",
            "sound_license": "cc-by,cc0,cc-by-nc",
            "page": page,
            "per_page": min(page_size, 200),
            "order": "desc",
            "order_by": "observed_on",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(API_BASE, params=params)
            response.raise_for_status()
            data = response.json()

        records: list[FederatedRecord] = []
        for obs in data.get("results", []):
            record = parse_observation(obs)
            if record:
                records.append(record)
        return records

    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        if not record.preview_url or record.license not in ("CC0", "CC-BY"):
            return None
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(record.preview_url)
            if response.status_code == 200:
                return response.content
        return None
