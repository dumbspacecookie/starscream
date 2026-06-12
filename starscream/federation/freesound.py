"""Freesound federation connector.

Harvests CC-BY/CC0 sounds via API v2. Stores preview MP3 when OAuth is unavailable;
full-quality download requires OAuth2 (future enhancement).

API docs: https://freesound.org/docs/api/
"""

from datetime import datetime, timezone

import httpx

from starscream.config import get_settings
from starscream.federation.base import FederatedRecord, FederationConnector
from starscream.federation.grounding import ground_federated_fields

API_BASE = "https://freesound.org/apiv2"
SEARCH_FIELDS = (
    "id,name,description,tags,license,created,username,duration,geotag,previews,url"
)

# Map Freesound license labels → Starscream license strings
LICENSE_MAP = {
    "Creative Commons 0": "CC0",
    "Attribution": "CC-BY",
    "Attribution NonCommercial": "CC-BY-NC",
    "Attribution NonCommercial NonDerivatives": "CC-BY-NC",
    "Attribution NonCommercial ShareAlike": "CC-BY-NC",
}

TAG_TAXONOMY = [
    (("bird", "birds", "songbird"), "WILDLIFE.BIRD"),
    (("dog", "bark", "canine"), "WILDLIFE.MAMMAL"),
    (("rain", "rainfall"), "ATMOSPHERIC.RAIN"),
    (("thunder", "storm"), "ATMOSPHERIC.THUNDER"),
    (("traffic", "car", "vehicle", "engine"), "URBAN.TRAFFIC"),
    (("crowd", "people", "chatter"), "URBAN.CROWD"),
    (("ocean", "wave", "sea"), "NATURAL.OCEAN"),
    (("forest", "wood", "tree"), "NATURAL.FOREST"),
    (("insect", "cricket", "cicada"), "WILDLIFE.INSECT"),
    (("music", "instrument"), "CULTURAL"),
    (("machine", "industrial", "motor"), "MECHANICAL"),
]


def map_license(freesound_license: str) -> str | None:
    for key, value in LICENSE_MAP.items():
        if key.lower() in freesound_license.lower():
            return value
    return None


def map_taxonomy(tags: list[str], name: str) -> str:
    haystack = " ".join(tags + [name]).lower()
    for keywords, code in TAG_TAXONOMY:
        if any(kw in haystack for kw in keywords):
            return code
    return "NATURAL"


def parse_sound(data: dict) -> FederatedRecord | None:
    license_raw = data.get("license", "")
    license_code = map_license(license_raw)
    if not license_code:
        return None

    geotag = data.get("geotag") or ""
    lat, lng = 0.0, 0.0
    if geotag:
        try:
            parts = geotag.replace(",", " ").split()
            if len(parts) >= 2:
                lat, lng = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    created = data.get("created")
    if created:
        recorded_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
    else:
        recorded_at = datetime.now(timezone.utc)

    tags = data.get("tags") or []
    name = data.get("name") or f"freesound-{data['id']}"
    norm_tags = [t.lower().replace(" ", "_") for t in tags]
    source_object, source_action = ground_federated_fields(title=name, tags=norm_tags)
    previews = data.get("previews") or {}
    preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

    return FederatedRecord(
        external_id=str(data["id"]),
        external_url=data.get("url") or f"https://freesound.org/sounds/{data['id']}/",
        taxonomy_code=map_taxonomy(tags, name),
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        license=license_code,
        title=name,
        description=data.get("description") or None,
        tags=norm_tags,
        duration_s=data.get("duration"),
        preview_url=preview_url,
        source_object=source_object,
        source_action=source_action,
        username=data.get("username"),
    )


class FreesoundConnector(FederationConnector):
    slug = "freesound"

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.freesound_api_key
        if not self.api_key:
            raise ValueError(
                "FREESOUND_API_KEY required — apply at https://freesound.org/apiv2/apply"
            )

    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        """Harvest CC-licensed sounds via text search (paginated)."""
        params = {
            "query": "*",
            "filter": 'license:"Creative Commons 0" OR license:"Attribution"',
            "fields": SEARCH_FIELDS,
            "page": page,
            "page_size": min(page_size, 150),
            "token": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_BASE}/search/text/", params=params)
            response.raise_for_status()
            data = response.json()

        records: list[FederatedRecord] = []
        for sound in data.get("results", []):
            record = parse_sound(sound)
            if record:
                records.append(record)
        return records

    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        if not record.preview_url:
            return None
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(record.preview_url)
            if response.status_code == 200:
                return response.content
        return None
