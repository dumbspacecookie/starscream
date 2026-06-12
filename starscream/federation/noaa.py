"""NOAA federation connector.

Harvests public-domain ocean acoustic samples from NOAA PMEL Acoustics Program
and NCEI passive acoustic archives. Uses a curated catalog of known PMEL WAV
URLs (whale vocalizations, seismic tremor, anthropogenic noise) with metadata
pointers to the NCEI passive acoustic data portal.

Source: https://www.pmel.noaa.gov/acoustics/
License: U.S. government work — public domain.
"""

from datetime import datetime, timezone

import httpx

from starscream.federation.base import FederatedRecord, FederationConnector

PMEL_BASE = "https://www.pmel.noaa.gov/acoustics"
NCEI_PAD_URL = "https://www.ncei.noaa.gov/products/passive-acoustic-data"
LICENSE = "PUBLIC_DOMAIN"
TAXONOMY = "AQUATIC"


def _pmel(path: str) -> str:
    return f"{PMEL_BASE}/{path.lstrip('/')}"


CURATED_CATALOG: list[dict] = [
    {
        "id": "pmel-nepblue24s10x",
        "title": "Blue Whale NE Pacific (10x)",
        "description": "Northeast Pacific blue whale call, time-compressed 10x for audition.",
        "preview_url": _pmel("whales/sounds/whalewav/nepblue24s10x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_blue.html"),
        "lat": 44.0,
        "lng": -125.0,
        "location_name": "Northeast Pacific",
        "source_object": "Balaenoptera musculus",
        "source_action": "vocalization",
        "tags": ["blue_whale", "baleen", "passive_acoustic", "pmel"],
    },
    {
        "id": "pmel-wblue26s10x",
        "title": "Blue Whale West Pacific (10x)",
        "description": "Western Pacific blue whale low-frequency call.",
        "preview_url": _pmel("whales/sounds/whalewav/wblue26s10x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_pacific.html"),
        "lat": 35.0,
        "lng": 140.0,
        "location_name": "Western Pacific",
        "source_object": "Balaenoptera musculus",
        "source_action": "vocalization",
        "tags": ["blue_whale", "pacific", "pmel"],
    },
    {
        "id": "pmel-etpb3-south-pacific",
        "title": "Blue Whale South Pacific (10x)",
        "description": "Southern Pacific blue whale recording from PMEL archive.",
        "preview_url": _pmel(
            "whales/sounds/whalewav/etpb3_10xc-BlueWhaleSouthPacific-10x.wav"
        ),
        "external_url": _pmel("whales/sounds/sounds_whales_blue.html"),
        "lat": -30.0,
        "lng": -120.0,
        "location_name": "South Pacific",
        "source_object": "Balaenoptera musculus",
        "source_action": "vocalization",
        "tags": ["blue_whale", "south_pacific", "pmel"],
    },
    {
        "id": "pmel-ak52-10x",
        "title": "52 Hz Whale Call (10x)",
        "description": "Unidentified 52 Hz whale-like call from NE Pacific hydrophones.",
        "preview_url": _pmel("whales/sounds/whalewav/ak52_10x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_blue.html"),
        "lat": 48.0,
        "lng": -145.0,
        "location_name": "Gulf of Alaska",
        "source_object": "unknown cetacean",
        "source_action": "vocalization",
        "tags": ["52hz", "mystery_whale", "pmel"],
    },
    {
        "id": "pmel-akhumphi1x",
        "title": "Humpback Whale Pacific",
        "description": "Humpback whale vocalization from Pacific hydrophone array.",
        "preview_url": _pmel("whales/sounds/whalewav/akhumphi1x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_pacific.html"),
        "lat": 20.0,
        "lng": -160.0,
        "location_name": "Central Pacific",
        "source_object": "Megaptera novaeangliae",
        "source_action": "song",
        "tags": ["humpback", "whale", "pmel"],
    },
    {
        "id": "pmel-atlblue-10x",
        "title": "Blue Whale Atlantic (10x)",
        "description": "Atlantic blue whale call from Mid-Atlantic Ridge hydrophones.",
        "preview_url": _pmel("whales/sounds/whalewav/atlblue_512_64_0-50_10x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_atlantic.html"),
        "lat": 35.0,
        "lng": -40.0,
        "location_name": "Mid-Atlantic",
        "source_object": "Balaenoptera musculus",
        "source_action": "vocalization",
        "tags": ["blue_whale", "atlantic", "pmel"],
    },
    {
        "id": "pmel-atlfin-10x",
        "title": "Fin Whale Atlantic (10x)",
        "description": "Atlantic fin whale 20 Hz pulse train.",
        "preview_url": _pmel(
            "whales/sounds/whalewav/atlfin_128_64_0-50-FinWhaleAtlantic-10x.wav"
        ),
        "external_url": _pmel("whales/sounds/sounds_whales_atlantic.html"),
        "lat": 42.0,
        "lng": -50.0,
        "location_name": "North Atlantic",
        "source_object": "Balaenoptera physalus",
        "source_action": "vocalization",
        "tags": ["fin_whale", "atlantic", "pmel"],
    },
    {
        "id": "pmel-atlmin-10x",
        "title": "Minke Whale Atlantic (10x)",
        "description": "Atlantic minke whale pulse train from passive acoustic mooring.",
        "preview_url": _pmel("whales/sounds/whalewav/atlmin_512_64_0-50_10x.wav"),
        "external_url": _pmel("whales/sounds/sounds_whales_atlantic.html"),
        "lat": 55.0,
        "lng": -30.0,
        "location_name": "North Atlantic",
        "source_object": "Balaenoptera acutorostrata",
        "source_action": "vocalization",
        "tags": ["minke_whale", "atlantic", "pmel"],
    },
    {
        "id": "pmel-tremor-japan-16x",
        "title": "Seismic Tremor South of Japan (16x)",
        "description": "Low-frequency seismic tremor recorded on ocean bottom hydrophone.",
        "preview_url": _pmel("sounds/tremorx16.wav"),
        "external_url": _pmel("sounds.html"),
        "lat": 28.0,
        "lng": 142.0,
        "location_name": "South of Japan",
        "source_object": "seafloor",
        "source_action": "seismic_tremor",
        "tags": ["seismic", "tremor", "hydrophone", "pmel"],
    },
    {
        "id": "pmel-airguns-10x",
        "title": "Seismic Airgun Survey (10x)",
        "description": "Anthropogenic airgun pulses from marine seismic survey.",
        "preview_url": _pmel("env-noise/sounds/airguns_00_03_05_marCE.wav"),
        "external_url": _pmel("sounds.html"),
        "lat": 10.0,
        "lng": -90.0,
        "location_name": "Eastern Tropical Pacific",
        "source_object": "survey vessel",
        "source_action": "airgun_pulse",
        "tags": ["anthropogenic", "airgun", "seismic_survey", "pmel"],
    },
    {
        "id": "pmel-equatorial-unknown-16x",
        "title": "Equatorial Pacific Unknown Source (16x)",
        "description": "Unidentified low-frequency sound from equatorial Pacific.",
        "preview_url": _pmel("sounds/noise97139.wav"),
        "external_url": _pmel("sounds.html"),
        "lat": 0.0,
        "lng": -140.0,
        "location_name": "Equatorial Pacific",
        "source_object": "unknown",
        "source_action": "ambient",
        "tags": ["unknown", "ambient", "pmel"],
    },
    {
        "id": "pmel-nets-blue-whale",
        "title": "NE Pacific Blue Whale AB Call",
        "description": "Blue whale AB call off the Oregon coast from PMEL multimedia.",
        "preview_url": _pmel("multimedia/NETS_bluWhale.wav"),
        "external_url": _pmel("multimedia.html"),
        "lat": 44.5,
        "lng": -125.5,
        "location_name": "Oregon Coast",
        "source_object": "Balaenoptera musculus",
        "source_action": "vocalization",
        "tags": ["blue_whale", "oregon", "pmel"],
    },
    {
        "id": "pmel-hb-ship-sbnms",
        "title": "Humpback with Ship — Stellwagen Bank",
        "description": "Humpback vocalizations with vessel noise, Stellwagen Bank NMS.",
        "preview_url": _pmel("multimedia/HB-ship-SBNMS.wav"),
        "external_url": _pmel("multimedia.html"),
        "lat": 42.3,
        "lng": -70.3,
        "location_name": "Stellwagen Bank National Marine Sanctuary",
        "source_object": "Megaptera novaeangliae",
        "source_action": "vocalization",
        "tags": ["humpback", "ship_noise", "sanctuary", "pmel"],
    },
    {
        "id": "pmel-hb-ship-amsnp",
        "title": "Humpback with Ship — American Samoa",
        "description": "Humpback whale vocalizations with snapping shrimp, American Samoa.",
        "preview_url": _pmel("multimedia/HB-ship-AMSNP.wav"),
        "external_url": _pmel("multimedia.html"),
        "lat": -14.3,
        "lng": -170.7,
        "location_name": "American Samoa National Park",
        "source_object": "Megaptera novaeangliae",
        "source_action": "vocalization",
        "tags": ["humpback", "american_samoa", "pmel"],
    },
    {
        "id": "pmel-damselfish-samoa",
        "title": "Damselfish — American Samoa Hydrophone",
        "description": "Damselfish territorial calls on reef hydrophone, American Samoa.",
        "preview_url": _pmel("multimedia/Damselfish Clip_American Samoa Hydrophone.wav"),
        "external_url": _pmel("multimedia.html"),
        "lat": -14.3,
        "lng": -170.7,
        "location_name": "American Samoa",
        "source_object": "damselfish",
        "source_action": "territorial_call",
        "tags": ["fish", "reef", "damselfish", "pmel"],
    },
    {
        "id": "ncei-pad-collection",
        "title": "NCEI Passive Acoustic Data Collection",
        "description": "Metadata pointer to NOAA NCEI passive acoustic archive (raw WAV/FLAC).",
        "preview_url": None,
        "external_url": NCEI_PAD_URL,
        "lat": 0.0,
        "lng": 0.0,
        "location_name": "Global oceans",
        "source_object": "passive acoustic archive",
        "source_action": "catalog",
        "tags": ["ncei", "archive", "passive_acoustic", "noaa"],
    },
]


def parse_entry(entry: dict) -> FederatedRecord:
    recorded_at = entry.get("recorded_at")
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc)
    elif isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))

    return FederatedRecord(
        external_id=entry["id"],
        external_url=entry["external_url"],
        taxonomy_code=TAXONOMY,
        lat=float(entry.get("lat", 0.0)),
        lng=float(entry.get("lng", 0.0)),
        recorded_at=recorded_at,
        license=LICENSE,
        title=entry.get("title"),
        description=entry.get("description"),
        tags=list(entry.get("tags") or []),
        location_name=entry.get("location_name"),
        preview_url=entry.get("preview_url"),
        source_object=entry.get("source_object"),
        source_action=entry.get("source_action"),
        duration_s=entry.get("duration_s"),
    )


class NOAAConnector(FederationConnector):
    slug = "noaa"

    def __init__(self, catalog: list[dict] | None = None):
        self.catalog = catalog if catalog is not None else CURATED_CATALOG

    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        start = (page - 1) * page_size
        end = start + page_size
        slice_ = self.catalog[start:end]
        return [parse_entry(entry) for entry in slice_]

    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        if not record.preview_url:
            return None
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(record.preview_url)
            if response.status_code == 200:
                return response.content
        return None
