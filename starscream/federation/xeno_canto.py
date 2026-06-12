"""Xeno-canto federation connector.

Harvests field-recorded wildlife sounds via API v3 (birds, bats, frogs,
grasshoppers, soundscapes). CC-BY-NC content is pointer-only locally.

API docs: https://xeno-canto.org/explore/api
"""

from datetime import datetime, timezone

import httpx

from starscream.config import get_settings
from starscream.federation.base import FederatedRecord, FederationConnector

API_BASE = "https://xeno-canto.org/api/3/recordings"
DEFAULT_QUERY = "grp:birds"

GRP_TAXONOMY = {
    "birds": "WILDLIFE.BIRD",
    "bats": "WILDLIFE.MAMMAL",
    "frogs": "WILDLIFE.MAMMAL",
    "grasshoppers": "WILDLIFE.INSECT",
    "soundscapes": "NATURAL",
    "land mammals": "WILDLIFE.MAMMAL",
}

LICENSE_PATTERNS = [
    ("by-nc", "CC-BY-NC"),
    ("by/4", "CC-BY"),
    ("by/3", "CC-BY"),
    ("zero", "CC0"),
]


def map_license(license_url: str) -> str | None:
    lower = (license_url or "").lower()
    for pattern, code in LICENSE_PATTERNS:
        if pattern in lower:
            return code
    return None


def map_taxonomy_from_grp(grp: str | None) -> str:
    if not grp:
        return "WILDLIFE.BIRD"
    return GRP_TAXONOMY.get(grp.strip().lower(), "WILDLIFE.BIRD")


def map_source_action(type_str: str | None) -> str:
    if not type_str:
        return "vocalization"
    primary = type_str.split(",")[0].strip().lower()
    return primary.replace(" ", "_") or "vocalization"


def _parse_float(value: str | float | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_longitude(data: dict) -> float:
    for key in ("lon", "lng"):
        val = data.get(key)
        if val not in (None, ""):
            return _parse_float(val)
    return 0.0


def _parse_duration(length: str | int | float | None) -> float | None:
    if length in (None, ""):
        return None
    if isinstance(length, (int, float)):
        return float(length)
    text = str(length).strip()
    if ":" in text:
        parts = text.split(":")
        try:
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return float(minutes * 60 + seconds)
            if len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return float(hours * 3600 + minutes * 60 + seconds)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_recorded_at(data: dict) -> datetime:
    date_str = data.get("date") or ""
    time_str = data.get("time") or "00:00"
    if date_str:
        try:
            return datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _normalize_url(url: str | None, fallback: str) -> str:
    if not url:
        return fallback
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _is_restricted(data: dict) -> bool:
    meta = data.get("_meta") or {}
    redacted = meta.get("redacted_fields") or {}
    if redacted.get("file") == "restricted_species":
        return True
    return "file" in redacted


def _species_label(data: dict) -> str:
    english = (data.get("en") or "").strip()
    if english:
        return english
    genus = (data.get("gen") or "").strip()
    species = (data.get("sp") or "").strip()
    if genus and species:
        return f"{genus} {species}"
    return f"xeno-canto-{data.get('id', 'unknown')}"


def parse_recording(data: dict) -> FederatedRecord | None:
    license_code = map_license(data.get("lic") or "")
    if not license_code:
        return None

    record_id = str(data["id"])
    species = _species_label(data)
    sound_type = data.get("type") or ""
    grp = data.get("grp")

    tags: list[str] = ["xeno-canto", "field_recording"]
    if grp:
        tags.append(f"grp_{grp.lower().replace(' ', '_')}")
    if sound_type:
        tags.extend(t.strip().lower().replace(" ", "_") for t in sound_type.split(","))
    quality = data.get("q")
    if quality:
        tags.append(f"quality_{str(quality).lower()}")
    country = data.get("cnt")
    if country:
        tags.append(str(country).lower().replace(" ", "_"))
    method = data.get("method")
    if method:
        tags.append(method.lower().replace(" ", "_"))

    restricted = _is_restricted(data)
    if restricted:
        tags.append("restricted_species")

    description_parts = [
        p
        for p in (
            data.get("loc"),
            data.get("cnt"),
            f"Recordist: {data['rec']}" if data.get("rec") else None,
            f"Method: {method}" if method else None,
            data.get("rmk"),
            "Location/audio redacted (restricted species)" if restricted else None,
        )
        if p
    ]

    page_url = _normalize_url(data.get("url"), f"https://xeno-canto.org/{record_id}")
    preview_url = None if restricted else _normalize_url(data.get("file"), "")

    return FederatedRecord(
        external_id=record_id,
        external_url=page_url,
        taxonomy_code=map_taxonomy_from_grp(grp),
        lat=_parse_float(data.get("lat")),
        lng=_parse_longitude(data),
        recorded_at=_parse_recorded_at(data),
        license=license_code,
        title=f"{species} — {sound_type}" if sound_type else species,
        description=" | ".join(description_parts) or None,
        tags=tags,
        location_name=None if restricted else (data.get("loc") or None),
        country_code=None,
        duration_s=_parse_duration(data.get("length")),
        preview_url=preview_url or None,
        source_object=species,
        source_action=map_source_action(sound_type),
        username=data.get("rec"),
    )


class XenoCantoConnector(FederationConnector):
    slug = "xeno-canto"

    def __init__(self, query: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.xeno_canto_api_key
        if not self.api_key:
            raise ValueError(
                "XENO_CANTO_API_KEY required — retrieve at https://xeno-canto.org/account"
            )
        self.query = query or DEFAULT_QUERY

    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        per_page = max(50, min(page_size, 500))
        params = {
            "query": self.query,
            "page": page,
            "key": self.api_key,
            "per_page": per_page,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(API_BASE, params=params)
            response.raise_for_status()
            data = response.json()

        records: list[FederatedRecord] = []
        for item in data.get("recordings", [])[:page_size]:
            record = parse_recording(item)
            if record:
                records.append(record)
        return records

    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        if record.license == "CC-BY-NC":
            return None
        if not record.preview_url:
            return None
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(record.preview_url)
            if response.status_code == 200:
                return response.content
        return None
