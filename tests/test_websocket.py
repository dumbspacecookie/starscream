import pytest
from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.events import StreamFilter, get_broadcaster

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_broadcaster():
    get_broadcaster().reset()
    yield
    get_broadcaster().reset()


def _sample_summary(**overrides):
    summary = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "taxonomy_code": "WILDLIFE.BIRD.PASSERINE",
        "location": {"lat": 40.758, "lng": -73.985},
        "recorded_at": "2024-06-15T10:00:00+00:00",
        "title": "Robin song",
        "source_id": "660e8400-e29b-41d4-a716-446655440001",
        "license": "CC0",
        "is_contribution": False,
        "is_duplicate": False,
        "duration_s": 12.5,
        "location_name": "Central Park",
        "country_code": "US",
    }
    summary.update(overrides)
    return summary


def test_stream_filter_taxonomy_prefix():
    stream_filter = StreamFilter(taxonomy_prefix="WILDLIFE")
    assert stream_filter.matches(_sample_summary())
    assert not stream_filter.matches(_sample_summary(taxonomy_code="HUMAN.MADE.DOOR"))


def test_stream_filter_bbox():
    stream_filter = StreamFilter(lat=40.758, lng=-73.985, radius_km=5)
    assert stream_filter.matches(_sample_summary())
    assert not stream_filter.matches(
        _sample_summary(location={"lat": 51.507, "lng": -0.128})
    )


def test_websocket_subscribe_ack():
    with client.websocket_connect("/v1/stream/ingest?taxonomy=WILDLIFE") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "subscribed"
        assert message["filter"]["taxonomy_prefix"] == "WILDLIFE"


def test_websocket_receives_matching_ingest_event():
    with client.websocket_connect("/v1/stream/ingest") as websocket:
        subscribed = websocket.receive_json()
        assert subscribed["type"] == "subscribed"

        summary = _sample_summary()
        get_broadcaster().publish(summary)

        event = websocket.receive_json()
        assert event["type"] == "ingest"
        assert event["recording"]["id"] == summary["id"]
        assert event["recording"]["taxonomy_code"] == summary["taxonomy_code"]


def test_websocket_taxonomy_filter_blocks_non_matching():
    with client.websocket_connect("/v1/stream/ingest?taxonomy=WILDLIFE") as websocket:
        websocket.receive_json()

        get_broadcaster().publish(_sample_summary(taxonomy_code="HUMAN.MADE.DOOR"))
        get_broadcaster().publish(_sample_summary(taxonomy_code="WILDLIFE.BIRD"))

        event = websocket.receive_json()
        assert event["recording"]["taxonomy_code"].startswith("WILDLIFE")


def test_websocket_subscribe_via_initial_message():
    with client.websocket_connect("/v1/stream/ingest") as websocket:
        websocket.send_json(
            {
                "taxonomy_prefix": "WILDLIFE",
                "lat": 40.758,
                "lng": -73.985,
                "radius_km": 10,
            }
        )
        message = websocket.receive_json()
        assert message["type"] == "subscribed"
        assert message["filter"]["taxonomy_prefix"] == "WILDLIFE"
        assert message["filter"]["radius_km"] == 10
