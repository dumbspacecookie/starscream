from unittest.mock import patch

import httpx

from starscream.pipeline.cross_modal import (
    enrich_cross_modal,
    fetch_osm_features,
    pick_primary_feature,
)

OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "way",
            "id": 1001,
            "center": {"lat": 40.781, "lon": -73.969},
            "tags": {"building": "yes", "name": "Metropolitan Museum"},
        },
        {
            "type": "node",
            "id": 2002,
            "lat": 40.7805,
            "lon": -73.968,
            "tags": {"amenity": "cafe", "name": "Park Cafe"},
        },
        {
            "type": "way",
            "id": 3003,
            "center": {"lat": 40.782, "lon": -73.97},
            "tags": {"highway": "footway", "name": "East Drive"},
        },
    ]
}


@patch("starscream.pipeline.cross_modal.httpx.post")
def test_fetch_osm_features_success(mock_post):
    mock_response = mock_post.return_value
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = OVERPASS_RESPONSE

    features = fetch_osm_features(40.78, -73.97, radius_m=100)

    assert len(features) == 3
    assert all("type" in f and "distance_m" in f and "osm_id" in f for f in features)
    assert features[0]["distance_m"] <= features[-1]["distance_m"]
    assert any(f["type"] == "building" for f in features)
    mock_post.assert_called_once()


@patch("starscream.pipeline.cross_modal.httpx.post")
def test_fetch_osm_features_failure(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timeout")

    assert fetch_osm_features(0.0, 0.0) == []


def test_pick_primary_feature_closest():
    features = [
        {"type": "highway", "name": "Road", "osm_id": 1, "distance_m": 80.0},
        {"type": "building", "name": "Hall", "osm_id": 2, "distance_m": 25.0},
        {"type": "natural", "name": "Pond", "osm_id": 3, "distance_m": 40.0},
    ]
    primary = pick_primary_feature(features)
    assert primary["type"] == "building"
    assert primary["osm_id"] == 2


def test_pick_primary_feature_empty():
    assert pick_primary_feature([]) is None


@patch("starscream.pipeline.cross_modal.fetch_osm_features")
def test_enrich_cross_modal(mock_fetch):
    mock_fetch.return_value = [
        {"type": "building", "name": "Metropolitan Museum", "osm_id": 1001, "distance_m": 12.5},
        {"type": "amenity", "name": "Park Cafe", "osm_id": 2002, "distance_m": 45.0},
    ]

    result = enrich_cross_modal(40.78, -73.97)

    assert result["osm_primary_type"] == "building"
    assert result["osm_primary_name"] == "Metropolitan Museum"
    assert result["osm_primary_id"] == 1001
    assert result["osm_primary_distance_m"] == 12.5
    assert len(result["nearby_features"]) == 2
    assert result["primary"]["type"] == "building"
