from unittest.mock import AsyncMock, patch

import pytest

from starscream.federation.internet_archive import (
    InternetArchiveConnector,
    POINTER_ONLY,
    map_license,
    map_taxonomy,
    parse_item,
)

SAMPLE_ITEM = {
    "identifier": "opensource_audio_example",
    "title": "Forest birds field recording",
    "description": "Bird songs recorded in a woodland setting.",
    "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
}

SAMPLE_ITEM_MIXED = {
    "identifier": "mixed_license_tape",
    "title": "Vintage radio broadcast",
    "description": "Historical broadcast with unclear rights.",
    "licenseurl": "",
}

SAMPLE_ITEM_CC0 = {
    "identifier": "public_domain_rain",
    "title": "Rain on tin roof",
    "description": "Atmospheric rainfall recording.",
    "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
}

SAMPLE_API_RESPONSE = {
    "response": {
        "numFound": 2,
        "start": 0,
        "docs": [SAMPLE_ITEM, SAMPLE_ITEM_MIXED],
    }
}

SAMPLE_METADATA = {
    "files": [
        {"name": "cover.jpg", "format": "JPEG"},
        {"name": "recording.mp3", "format": "VBR MP3"},
    ]
}


def test_map_license_by():
    assert map_license("https://creativecommons.org/licenses/by/4.0/") == "CC-BY"


def test_map_license_cc0():
    assert map_license("https://creativecommons.org/publicdomain/zero/1.0/") == "CC0"


def test_map_license_by_nc():
    assert map_license("https://creativecommons.org/licenses/by-nc/3.0/") == "CC-BY-NC"


def test_map_license_unknown_defaults_pointer_only():
    assert map_license("https://example.com/all-rights-reserved") == POINTER_ONLY
    assert map_license(None) == POINTER_ONLY


def test_map_taxonomy_bird_from_title():
    assert map_taxonomy("Forest birds field recording", None) == "WILDLIFE.BIRD"


def test_map_taxonomy_rain_from_description():
    assert map_taxonomy("Ambient sounds", "Heavy rainfall on pavement") == "ATMOSPHERIC.RAIN"


def test_map_taxonomy_default():
    assert map_taxonomy("Unknown clip", None) == "NATURAL"


def test_parse_item_cc_by():
    record = parse_item(SAMPLE_ITEM)
    assert record is not None
    assert record.external_id == "opensource_audio_example"
    assert record.external_url == "https://archive.org/details/opensource_audio_example"
    assert record.license == "CC-BY"
    assert record.taxonomy_code == "WILDLIFE.BIRD"
    assert record.title == "Forest birds field recording"
    assert record.preview_url is None
    assert record.source_action == "vocalizing"
    assert "bird" in record.source_object.lower() or record.source_object == "forest"


def test_parse_item_mixed_license_pointer_only():
    record = parse_item(SAMPLE_ITEM_MIXED)
    assert record is not None
    assert record.license == POINTER_ONLY
    assert record.external_url == "https://archive.org/details/mixed_license_tape"


def test_parse_item_rain_grounding():
    record = parse_item(SAMPLE_ITEM_CC0)
    assert record is not None
    assert record.source_action == "falling"
    assert record.taxonomy_code == "ATMOSPHERIC.RAIN"


def test_parse_item_skips_missing_identifier():
    assert parse_item({"title": "No id"}) is None


@pytest.mark.asyncio
async def test_harvest_page_parses_api_response():
    connector = InternetArchiveConnector()

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: SAMPLE_API_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "starscream.federation.internet_archive.httpx.AsyncClient",
        return_value=mock_client,
    ):
        records = await connector.harvest_page(page=1, page_size=10)

    assert len(records) == 2
    assert records[0].license == "CC-BY"
    assert records[1].license == POINTER_ONLY
    mock_client.get.assert_awaited_once()
    call_kwargs = mock_client.get.await_args
    assert call_kwargs.args[0] == "https://archive.org/advancedsearch.php"
    params = dict(call_kwargs.kwargs["params"])
    assert params["q"] == "collection:opensource_audio OR mediatype:audio"
    assert params["rows"] == 10
    assert params["page"] == 1


@pytest.mark.asyncio
async def test_download_preview_pointer_only_skipped():
    record = parse_item(SAMPLE_ITEM_MIXED)
    assert record is not None
    connector = InternetArchiveConnector()
    assert await connector.download_preview(record) is None


@pytest.mark.asyncio
async def test_download_preview_fetches_metadata_for_cc_by():
    record = parse_item(SAMPLE_ITEM)
    assert record is not None

    meta_response = AsyncMock()
    meta_response.status_code = 200
    meta_response.json = lambda: SAMPLE_METADATA

    audio_response = AsyncMock()
    audio_response.status_code = 200
    audio_response.content = b"fake-mp3-bytes"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[meta_response, audio_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    connector = InternetArchiveConnector()
    with patch(
        "starscream.federation.internet_archive.httpx.AsyncClient",
        return_value=mock_client,
    ):
        data = await connector.download_preview(record)

    assert data == b"fake-mp3-bytes"
    assert mock_client.get.await_count == 2


@pytest.mark.asyncio
async def test_download_preview_cc0():
    record = parse_item(SAMPLE_ITEM_CC0)
    assert record is not None
    assert record.license == "CC0"

    meta_response = AsyncMock()
    meta_response.status_code = 200
    meta_response.json = lambda: SAMPLE_METADATA

    audio_response = AsyncMock()
    audio_response.status_code = 200
    audio_response.content = b"rain-audio"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[meta_response, audio_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    connector = InternetArchiveConnector()
    with patch(
        "starscream.federation.internet_archive.httpx.AsyncClient",
        return_value=mock_client,
    ):
        data = await connector.download_preview(record)

    assert data == b"rain-audio"
