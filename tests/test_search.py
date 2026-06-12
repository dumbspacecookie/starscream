from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from starscream.api.main import app

client = TestClient(app)

SAMPLE_HIT = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Door slam",
    "source_object": "wooden door",
    "source_action": "slamming shut",
    "description": "Interior door slam",
    "tags": ["door", "indoor"],
    "material": "wood",
    "environment": "indoor",
    "taxonomy_code": "HUMAN.MADE.DOOR",
    "location_name": "Apartment",
    "country_code": "US",
    "habitat": "urban",
    "season": "summer",
    "quality": 4,
    "is_contribution": True,
    "recorded_at": "2024-06-15T10:00:00+00:00",
    "lat": 40.758,
    "lng": -73.985,
}


def _mock_meili_search(return_value: dict):
    index = MagicMock()
    index.search.return_value = return_value
    meili_client = MagicMock()
    meili_client.index.return_value = index
    return patch("starscream.api.routes.search._client", return_value=meili_client), index


def test_search_endpoint_in_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/v1/search" in paths


def test_search_returns_hits():
    search_result = {
        "hits": [SAMPLE_HIT],
        "query": "door",
        "estimatedTotalHits": 1,
        "processingTimeMs": 3,
    }
    mock_patch, index = _mock_meili_search(search_result)
    with mock_patch:
        response = client.get("/v1/search", params={"q": "door", "limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "door"
    assert data["limit"] == 10
    assert data["total"] == 1
    assert data["processing_time_ms"] == 3
    assert len(data["hits"]) == 1
    hit = data["hits"][0]
    assert hit["title"] == "Door slam"
    assert hit["taxonomy_code"] == "HUMAN.MADE.DOOR"
    assert hit["is_contribution"] is True
    assert UUID(hit["id"]) == UUID(SAMPLE_HIT["id"])

    index.search.assert_called_once()
    call_args = index.search.call_args
    assert call_args[0][0] == "door"
    assert call_args[0][1]["limit"] == 10
    assert "filter" not in call_args[0][1]


def test_search_applies_filters():
    search_result = {"hits": [], "query": "rain", "estimatedTotalHits": 0, "processingTimeMs": 1}
    mock_patch, index = _mock_meili_search(search_result)
    with mock_patch:
        response = client.get(
            "/v1/search",
            params={
                "q": "rain",
                "taxonomy": "WILDLIFE",
                "country": "US",
                "material": "wood",
                "is_contribution": "true",
            },
        )

    assert response.status_code == 200
    filter_expr = index.search.call_args[0][1]["filter"]
    assert 'taxonomy_code STARTS WITH "WILDLIFE"' in filter_expr
    assert 'country_code = "US"' in filter_expr
    assert 'material = "wood"' in filter_expr
    assert "is_contribution = true" in filter_expr


def test_search_unavailable_returns_503():
    with patch("starscream.api.routes.search._client", return_value=None):
        response = client.get("/v1/search", params={"q": "door"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Search service unavailable"
