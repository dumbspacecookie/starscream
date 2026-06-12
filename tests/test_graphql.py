import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.db.models import LicenseType, RecorderType, ReviewStatus, Season

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


def _mock_recording(**overrides):
    rec_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": rec_id,
        "spectral_hash": "abc123",
        "taxonomy_code": "WILDLIFE.BIRD",
        "recorded_at": datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc),
        "source_id": uuid.uuid4(),
        "license": LicenseType.CC0,
        "title": "Robin song",
        "description": None,
        "source_object": None,
        "source_action": None,
        "tags": ["bird"],
        "material": None,
        "environment": "outdoor",
        "world_model_labels": None,
        "contributor_id": None,
        "contributor_name": None,
        "recorder_model": None,
        "sample_rate_hz": 48000,
        "channels": 2,
        "bit_depth": 24,
        "is_contribution": False,
        "location_name": "Central Park",
        "country_code": "US",
        "altitude_m": None,
        "season": Season.SUMMER,
        "habitat": "urban",
        "weather": None,
        "temperature_c": None,
        "cross_modal_links": None,
        "recorder_type": RecorderType.SMARTPHONE,
        "quality": 4,
        "review_status": ReviewStatus.UNREVIEWED,
        "external_id": None,
        "external_url": None,
        "duration_s": 12.5,
        "flac_key": "flac/test.flac",
        "canonical_id": None,
        "is_duplicate": False,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _graphql(query: str, variables: dict | None = None):
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    return client.post("/v1/graphql", json=payload)


def test_graphiql_served_at_graphql_path():
    response = client.get("/graphql")
    assert response.status_code == 200
    assert "graphiql" in response.text.lower()


def test_graphql_api_has_no_graphiql():
    response = client.get("/v1/graphql")
    assert response.status_code in (404, 405)


def test_recordings_query():
    rec = _mock_recording()
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [(rec, 40.758, -73.985)]

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = _graphql(
            """
            query {
              recordings(taxonomy: "WILDLIFE", qualityMin: 3, limit: 10) {
                id
                taxonomyCode
                quality
                location { lat lng }
              }
            }
            """
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body
    items = body["data"]["recordings"]
    assert len(items) == 1
    assert items[0]["taxonomyCode"] == "WILDLIFE.BIRD"
    assert items[0]["quality"] == 4
    assert items[0]["location"]["lat"] == 40.758


def test_recording_by_id():
    rec_id = uuid.uuid4()
    rec = _mock_recording(id=rec_id)
    mock_db = MagicMock()
    mock_db.execute.return_value.one_or_none.return_value = (rec, 51.5, -0.1)

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = _graphql(
            """
            query ($id: ID!) {
              recording(id: $id) {
                id
                title
                hasAudio
              }
            }
            """,
            {"id": str(rec_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]["recording"]
    assert data["id"] == str(rec_id)
    assert data["title"] == "Robin song"
    assert data["hasAudio"] is True


def test_recording_not_found_returns_null():
    mock_db = MagicMock()
    mock_db.execute.return_value.one_or_none.return_value = None

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = _graphql(
            """
            query {
              recording(id: "550e8400-e29b-41d4-a716-446655440000") {
                id
              }
            }
            """
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"]["recording"] is None


def test_search_query():
    search_result = {
        "hits": [SAMPLE_HIT],
        "query": "door",
        "estimatedTotalHits": 1,
        "processingTimeMs": 3,
    }
    index = MagicMock()
    index.search.return_value = search_result
    meili_client = MagicMock()
    meili_client.index.return_value = index

    with patch("starscream.api.graphql.schema._client", return_value=meili_client):
        response = _graphql(
            """
            query {
              search(q: "door", limit: 5) {
                query
                total
                hits { title taxonomyCode }
              }
            }
            """
        )

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body
    search = body["data"]["search"]
    assert search["query"] == "door"
    assert search["total"] == 1
    assert search["hits"][0]["title"] == "Door slam"


@patch("starscream.api.stats_helpers.flac_storage_bytes", return_value=0)
def test_stats_query(_mock_storage):
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [100, 5, 12, 8, 20, 50]

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = _graphql(
            """
            query {
              stats {
                totalRecordings
                totalSources
                countriesCovered
                taxonomyBranches
                totalContributions
                totalTags
              }
            }
            """
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    stats = response.json()["data"]["stats"]
    assert stats["totalRecordings"] == 100
    assert stats["totalSources"] == 5
    assert stats["countriesCovered"] == 12
    assert stats["totalContributions"] == 20
    assert stats["totalTags"] == 50
