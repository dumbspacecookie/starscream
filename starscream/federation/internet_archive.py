"""Internet Archive federation connector.

Harvests open audio from archive.org advanced search. Many items carry mixed or
unclear licensing — those are stored as pointer-only metadata with external URLs.
CC-BY and CC0 items may download audio when permitted.

API: https://archive.org/advancedsearch.php
"""

from datetime import datetime, timezone

import httpx

from starscream.federation.base import FederatedRecord, FederationConnector
from starscream.federation.grounding import ground_federated_fields

API_BASE = "https://archive.org/advancedsearch.php"
METADATA_BASE = "https://archive.org/metadata"
DOWNLOAD_BASE = "https://archive.org/download"
DEFAULT_QUERY = "collection:opensource_audio OR mediatype:audio"
POINTER_ONLY = "POINTER-ONLY"
PODCAST_HINTS = ("podcast", "episode", "npr", "pri", "radio", "broadcast", "feed")

LICENSE_PATTERNS = [
    ("by-nc", "CC-BY-NC"),
    ("by/4", "CC-BY"),
    ("by/3", "CC-BY"),
    ("by/2", "CC-BY"),
    ("zero", "CC0"),
    ("publicdomain/zero", "CC0"),
    ("publicdomain/mark", "CC0"),
]

TAG_TAXONOMY = [
    (("bird", "birds", "songbird", "ornithology"), "WILDLIFE.BIRD"),
    (("dog", "bark", "canine", "mammal"), "WILDLIFE.MAMMAL"),
    (("rain", "rainfall"), "ATMOSPHERIC.RAIN"),
    (("thunder", "storm"), "ATMOSPHERIC.THUNDER"),
    (("traffic", "car", "vehicle", "engine"), "URBAN.TRAFFIC"),
    (("crowd", "people", "chatter", "speech"), "URBAN.CROWD"),
    (("ocean", "wave", "sea"), "NATURAL.OCEAN"),
    (("forest", "wood", "tree"), "NATURAL.FOREST"),
    (("insect", "cricket", "cicada"), "WILDLIFE.INSECT"),
    (("music", "instrument", "symphony"), "CULTURAL"),
    (("machine", "industrial", "motor"), "MECHANICAL"),
    (("radio", "broadcast", "podcast"), "CULTURAL"),
    (("nature", "ambient", "field recording"), "NATURAL"),
]

AUDIO_EXTENSIONS = (".mp3", ".ogg", ".flac", ".wav", ".m4a", ".aac")


def map_license(license_url: str | None) -> str:
    lower = (license_url or "").lower()
    for pattern, code in LICENSE_PATTERNS:
        if pattern in lower:
            return code
    return POINTER_ONLY


def map_taxonomy(title: str, description: str | None) -> str:
    haystack = f"{title} {description or ''}".lower()
    for keywords, code in TAG_TAXONOMY:
        if any(kw in haystack for kw in keywords):
            return code
    return "NATURAL"


def _pick_audio_file(files: list[dict]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for f in files:
        name = f.get("name") or ""
        lower = name.lower()
        if not any(lower.endswith(ext) for ext in AUDIO_EXTENSIONS):
            continue
        fmt = (f.get("format") or "").lower()
        priority = 0
        if "mp3" in lower or "mp3" in fmt:
            priority = 3
        elif "ogg" in lower or "vorbis" in fmt:
            priority = 2
        elif "flac" in lower or "flac" in fmt:
            priority = 1
        candidates.append((priority, name))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


async def resolve_audio_url(client: httpx.AsyncClient, identifier: str) -> str | None:
    response = await client.get(f"{METADATA_BASE}/{identifier}")
    if response.status_code != 200:
        return None
    data = response.json()
    filename = _pick_audio_file(data.get("files") or [])
    if not filename:
        return None
    return f"{DOWNLOAD_BASE}/{identifier}/{filename}"


def parse_item(data: dict) -> FederatedRecord | None:
    identifier = data.get("identifier")
    if not identifier:
        return None

    title = (data.get("title") or identifier).strip()
    description = data.get("description")
    if isinstance(description, list):
        description = " ".join(str(d) for d in description if d)
    description = (description or "").strip() or None

    license_code = map_license(data.get("licenseurl"))
    license_url = (data.get("licenseurl") or "").strip()

    tags: list[str] = []
    haystack = f"{title} {description or ''}".lower()
    if any(hint in haystack for hint in PODCAST_HINTS):
        tags.append("podcast")
    if license_url:
        tags.append("licensed")
    for word in title.lower().split():
        cleaned = word.strip(".,;:!?\"'()[]")
        if len(cleaned) > 2:
            tags.append(cleaned.replace(" ", "_"))

    grounding_tags = [t for t in tags if t not in ("licensed", "podcast")]
    source_object, source_action = ground_federated_fields(
        title=title, tags=grounding_tags[:20]
    )

    desc_parts = []
    if description:
        desc_parts.append(description)
    if license_url:
        desc_parts.append(f"License: {license_url}")

    return FederatedRecord(
        external_id=identifier,
        external_url=f"https://archive.org/details/{identifier}",
        taxonomy_code=map_taxonomy(title, description),
        lat=0.0,
        lng=0.0,
        recorded_at=datetime.now(timezone.utc),
        license=license_code,
        title=title,
        description=" | ".join(desc_parts) or None,
        tags=tags[:20],
        preview_url=None,
        source_object=source_object,
        source_action=source_action,
    )


class InternetArchiveConnector(FederationConnector):
    slug = "internet-archive"

    def __init__(self, query: str | None = None):
        self.query = query or DEFAULT_QUERY

    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        params: list[tuple[str, str | int]] = [
            ("q", self.query),
            ("rows", page_size),
            ("page", page),
            ("output", "json"),
        ]
        for field in ("identifier", "title", "description", "licenseurl"):
            params.append(("fl[]", field))

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(API_BASE, params=params)
            response.raise_for_status()
            data = response.json()

        docs = (data.get("response") or {}).get("docs") or []
        records: list[FederatedRecord] = []
        for item in docs[:page_size]:
            record = parse_item(item)
            if record:
                records.append(record)
        return records

    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        if record.license not in ("CC0", "CC-BY"):
            return None
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            audio_url = record.preview_url or await resolve_audio_url(
                client, record.external_id
            )
            if not audio_url:
                return None
            response = await client.get(audio_url)
            if response.status_code == 200:
                return response.content
        return None
