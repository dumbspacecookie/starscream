from unittest.mock import AsyncMock, patch

import pytest

from starscream.federation.harvest import CONNECTORS
from starscream.federation.nasa import (
    CURATED_CATALOG as NASA_CATALOG,
    LICENSE as NASA_LICENSE,
    NASAConnector,
    TAXONOMY as NASA_TAXONOMY,
    parse_entry as parse_nasa_entry,
)
from starscream.federation.noaa import (
    CURATED_CATALOG as NOAA_CATALOG,
    LICENSE as NOAA_LICENSE,
    NOAAConnector,
    TAXONOMY as NOAA_TAXONOMY,
    parse_entry as parse_noaa_entry,
)

SAMPLE_NOAA = {
    "id": "pmel-test-blue",
    "title": "Test Blue Whale",
    "description": "Sample NOAA entry for tests.",
    "preview_url": "https://www.pmel.noaa.gov/acoustics/whales/sounds/whalewav/test.wav",
    "external_url": "https://www.pmel.noaa.gov/acoustics/whales/sounds/sounds_whales_blue.html",
    "lat": 44.0,
    "lng": -125.0,
    "location_name": "Northeast Pacific",
    "source_object": "Balaenoptera musculus",
    "source_action": "vocalization",
    "tags": ["blue_whale", "test"],
}

SAMPLE_NOAA_POINTER = {
    "id": "ncei-test-pointer",
    "title": "NCEI Archive Pointer",
    "description": "Metadata-only archive pointer.",
    "preview_url": None,
    "external_url": "https://www.ncei.noaa.gov/products/passive-acoustic-data",
    "lat": 0.0,
    "lng": 0.0,
    "source_object": "archive",
    "source_action": "catalog",
    "tags": ["ncei"],
}

SAMPLE_NASA = {
    "id": "nasa-test-mars-wind",
    "title": "Test Mars Wind",
    "description": "Sample NASA entry for tests.",
    "preview_url": "https://www.nasa.gov/wp-content/uploads/2024/05/test-mars.wav",
    "external_url": "https://www.nasa.gov/sounds-from-beyond/",
    "lat": 18.4,
    "lng": 77.5,
    "location_name": "Jezero Crater, Mars",
    "source_object": "Mars atmosphere",
    "source_action": "wind",
    "tags": ["mars", "test"],
}


def test_connectors_registered():
    assert "noaa" in CONNECTORS
    assert "nasa" in CONNECTORS
    assert CONNECTORS["noaa"] is NOAAConnector
    assert CONNECTORS["nasa"] is NASAConnector


def test_noaa_catalog_nonempty():
    assert len(NOAA_CATALOG) >= 10
    assert NOAA_LICENSE == "PUBLIC_DOMAIN"
    assert NOAA_TAXONOMY == "AQUATIC"


def test_nasa_catalog_size():
    assert 20 <= len(NASA_CATALOG) <= 50
    assert NASA_LICENSE == "PUBLIC_DOMAIN"
    assert NASA_TAXONOMY == "EXTRATERRESTRIAL"


def test_parse_noaa_entry_with_audio():
    record = parse_noaa_entry(SAMPLE_NOAA)
    assert record.external_id == "pmel-test-blue"
    assert record.license == "PUBLIC_DOMAIN"
    assert record.taxonomy_code == "AQUATIC"
    assert record.preview_url.endswith("test.wav")
    assert record.source_object == "Balaenoptera musculus"
    assert record.lat == 44.0


def test_parse_noaa_entry_pointer_only():
    record = parse_noaa_entry(SAMPLE_NOAA_POINTER)
    assert record.preview_url is None
    assert "ncei.noaa.gov" in record.external_url


def test_parse_nasa_entry():
    record = parse_nasa_entry(SAMPLE_NASA)
    assert record.external_id == "nasa-test-mars-wind"
    assert record.license == "PUBLIC_DOMAIN"
    assert record.taxonomy_code == "EXTRATERRESTRIAL"
    assert record.location_name == "Jezero Crater, Mars"
    assert "mars" in record.tags


@pytest.mark.asyncio
async def test_noaa_harvest_page_pagination():
    catalog = [SAMPLE_NOAA, SAMPLE_NOAA_POINTER]
    connector = NOAAConnector(catalog=catalog)

    page1 = await connector.harvest_page(page=1, page_size=1)
    page2 = await connector.harvest_page(page=2, page_size=1)
    page3 = await connector.harvest_page(page=3, page_size=1)

    assert len(page1) == 1
    assert page1[0].external_id == "pmel-test-blue"
    assert len(page2) == 1
    assert page2[0].external_id == "ncei-test-pointer"
    assert page3 == []


@pytest.mark.asyncio
async def test_nasa_harvest_page_returns_records():
    connector = NASAConnector(catalog=[SAMPLE_NASA])
    records = await connector.harvest_page(page=1, page_size=10)
    assert len(records) == 1
    assert records[0].taxonomy_code == "EXTRATERRESTRIAL"


@pytest.mark.asyncio
async def test_noaa_download_preview_fetches_wav():
    record = parse_noaa_entry(SAMPLE_NOAA)
    connector = NOAAConnector()

    audio_response = AsyncMock()
    audio_response.status_code = 200
    audio_response.content = b"fake-wav-bytes"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=audio_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("starscream.federation.noaa.httpx.AsyncClient", return_value=mock_client):
        data = await connector.download_preview(record)

    assert data == b"fake-wav-bytes"
    mock_client.get.assert_awaited_once_with(record.preview_url)


@pytest.mark.asyncio
async def test_noaa_download_preview_skips_without_url():
    record = parse_noaa_entry(SAMPLE_NOAA_POINTER)
    connector = NOAAConnector()
    assert await connector.download_preview(record) is None


@pytest.mark.asyncio
async def test_nasa_download_preview_fetches_mp3():
    record = parse_nasa_entry(SAMPLE_NASA)
    connector = NASAConnector()

    audio_response = AsyncMock()
    audio_response.status_code = 200
    audio_response.content = b"fake-mp3-bytes"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=audio_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("starscream.federation.nasa.httpx.AsyncClient", return_value=mock_client):
        data = await connector.download_preview(record)

    assert data == b"fake-mp3-bytes"
    mock_client.get.assert_awaited_once_with(record.preview_url)
