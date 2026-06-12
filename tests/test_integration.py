"""Cross-surface smoke tests — mocked dependencies (not real infra).

For the real upload→store→search path see tests/test_e2e.py (requires Docker).
"""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.federation.harvest import CONNECTORS

client = TestClient(app)

HEALTH_OK = {
    "dependencies": {
        "postgres": {"ok": True, "detail": "connected"},
        "meilisearch": {"ok": True, "detail": "available"},
        "minio": {"ok": True, "detail": "bucket reachable"},
    },
    "all_ok": True,
}

SEARCH_HIT = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Integration test sound",
    "taxonomy_code": "WILDLIFE.BIRD",
    "tags": ["bird"],
    "quality": 4,
}


@patch("starscream.api.main.check_dependencies", return_value=HEALTH_OK)
def test_integration_health(_mock_check):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["postgres"]["ok"] is True


def test_integration_explore_page():
    response = client.get("/explore")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/search" in response.text


def test_integration_search():
    index = MagicMock()
    index.search.return_value = {
        "hits": [SEARCH_HIT],
        "query": "bird",
        "estimatedTotalHits": 1,
        "processingTimeMs": 2,
    }
    meili_client = MagicMock()
    meili_client.index.return_value = index

    with patch("starscream.api.routes.search._client", return_value=meili_client):
        response = client.get("/v1/search", params={"q": "bird", "limit": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "bird"
    assert len(data["hits"]) == 1
    assert data["hits"][0]["title"] == "Integration test sound"


@patch("starscream.api.stats_helpers.flac_storage_bytes", return_value=0)
def test_integration_stats(_mock_storage):
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [42, 6, 10, 8, 15, 120]

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/v1/stats")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    stats = response.json()
    assert stats["total_recordings"] == 42
    assert stats["total_sources"] == 6
    assert stats["total_contributions"] == 15


def test_integration_governance():
    response = client.get("/v1/governance")
    assert response.status_code == 200
    body = response.json()
    assert body["foundation"]["name"] == "Starscream Foundation"
    assert "CC0" in body["license_policy"]["allowed_licenses"]


@pytest.mark.skipif(
    importlib.util.find_spec("strawberry") is None,
    reason="strawberry-graphql not installed (optional graphql extra)",
)
@patch("starscream.api.stats_helpers.flac_storage_bytes", return_value=0)
def test_integration_graphql(_mock_storage):
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [10, 3, 5, 4, 2, 20]

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/v1/graphql",
            json={"query": "{ stats { totalRecordings totalSources } }"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body
    stats = body["data"]["stats"]
    assert stats["totalRecordings"] == 10
    assert stats["totalSources"] == 3


def test_integration_harvest_connectors_import():
    expected = {
        "freesound",
        "xeno-canto",
        "inaturalist",
        "internet-archive",
        "noaa",
        "nasa",
    }
    assert set(CONNECTORS) == expected
    for slug, connector_cls in CONNECTORS.items():
        assert connector_cls.__name__.endswith("Connector"), slug
