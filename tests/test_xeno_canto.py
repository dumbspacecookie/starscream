from unittest.mock import AsyncMock, patch

import pytest

from starscream.federation.xeno_canto import (
    XenoCantoConnector,
    map_license,
    map_source_action,
    map_taxonomy_from_grp,
    parse_recording,
)

SAMPLE_RECORDING = {
    "id": "76967",
    "gen": "Turdus",
    "sp": "merula",
    "en": "Common Blackbird",
    "grp": "birds",
    "rec": "Bob Smith",
    "cnt": "Netherlands",
    "loc": "Amsterdam",
    "lat": "52.3676",
    "lon": "4.9041",
    "type": "song",
    "method": "field recording",
    "file": "//xeno-canto.org/76967/download",
    "lic": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "url": "https://xeno-canto.org/76967",
    "length": "4:08",
    "date": "2019-04-12",
    "time": "07:15",
    "q": "A",
}

SAMPLE_API_RESPONSE = {
    "numRecordings": "1",
    "numSpecies": "1",
    "page": 1,
    "numPages": 1,
    "recordings": [SAMPLE_RECORDING],
}


def test_map_license_by_nc():
    assert map_license("https://creativecommons.org/licenses/by-nc-sa/4.0/") == "CC-BY-NC"


def test_map_taxonomy_bats():
    assert map_taxonomy_from_grp("bats") == "WILDLIFE.MAMMAL"


def test_map_taxonomy_soundscapes():
    assert map_taxonomy_from_grp("soundscapes") == "NATURAL"


def test_map_source_action_song():
    assert map_source_action("song") == "song"


def test_parse_recording_v3_lon_and_duration():
    record = parse_recording(SAMPLE_RECORDING)
    assert record is not None
    assert record.external_id == "76967"
    assert record.lng == pytest.approx(4.9041)
    assert record.duration_s == pytest.approx(248.0)
    assert record.taxonomy_code == "WILDLIFE.BIRD"
    assert "field_recording" in record.tags
    assert "grp_birds" in record.tags


def test_parse_recording_restricted_species():
    restricted = {
        **SAMPLE_RECORDING,
        "file": "restricted_species",
        "_meta": {"redacted_fields": {"file": "restricted_species", "lat": "restricted_species"}},
    }
    record = parse_recording(restricted)
    assert record is not None
    assert record.preview_url is None
    assert "restricted_species" in record.tags


def test_connector_requires_api_key():
    with patch("starscream.federation.xeno_canto.get_settings") as mock_settings:
        mock_settings.return_value.xeno_canto_api_key = ""
        with pytest.raises(ValueError, match="XENO_CANTO_API_KEY"):
            XenoCantoConnector()


@pytest.mark.asyncio
async def test_harvest_page_sends_v3_params():
    connector = XenoCantoConnector(query="grp:birds", api_key="test-key")

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: SAMPLE_API_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("starscream.federation.xeno_canto.httpx.AsyncClient", return_value=mock_client):
        records = await connector.harvest_page(page=1, page_size=10)

    assert len(records) == 1
    call_kwargs = mock_client.get.await_args
    assert call_kwargs.kwargs["params"] == {
        "query": "grp:birds",
        "page": 1,
        "key": "test-key",
        "per_page": 50,
    }
