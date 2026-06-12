from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.federation.harvest import CONNECTORS
from starscream.jobs.harvest_all import DEFAULT_SOURCES

client = TestClient(app)
STATIC = Path(__file__).parent.parent / "starscream" / "static"


def test_explore_page_served():
    response = client.get("/explore")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/search" in response.text


def test_upload_has_explore_link():
    text = (STATIC / "upload.html").read_text(encoding="utf-8")
    assert 'href="/explore"' in text


def test_upload_has_similar_sounds_check():
    text = (STATIC / "upload.html").read_text(encoding="utf-8")
    assert "checkSimilarSounds" in text
    assert "/v1/search" in text
    assert "Similar sounds already in corpus" in text


def test_inaturalist_in_connectors():
    assert "inaturalist" in CONNECTORS


def test_harvest_all_default_sources():
    assert set(DEFAULT_SOURCES) == set(CONNECTORS.keys())
    assert "inaturalist" in DEFAULT_SOURCES
    assert "freesound" in DEFAULT_SOURCES
    assert "xeno-canto" in DEFAULT_SOURCES


def test_upload_similar_sounds_on_blur():
    text = (STATIC / "upload.html").read_text(encoding="utf-8")
    assert 'addEventListener("blur"' in text


def test_harvest_all_skips_unknown_source():
    session = MagicMock()
    with (
        patch("starscream.jobs.harvest_all.get_session_factory", return_value=lambda: session),
        patch("starscream.jobs.harvest_all.harvest_source_sync") as mock_harvest,
        patch("starscream.jobs.harvest_all.record_skipped") as mock_skipped,
    ):
        from starscream.jobs.harvest_all import harvest_all

        mock_harvest.side_effect = ValueError("Unknown source: bad")
        code = harvest_all(["bad"], pages=1)
    assert code == 1
    mock_skipped.assert_called_once()
