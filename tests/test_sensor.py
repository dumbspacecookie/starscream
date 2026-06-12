import base64
import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from pydantic import ValidationError

from starscream.sensor.mqtt_handler import (
    decode_audio_base64,
    parse_mqtt_payload,
    parse_topic,
    topic_for_node,
)
from starscream.sensor.node import (
    NodeRegistration,
    generate_node_token,
    hash_node_token,
    register_sensor_node,
)


def _make_wav_bytes(duration_s: float = 0.5, sr: int = 44100) -> bytes:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_node_registration_schema():
    reg = NodeRegistration(
        node_id="forest-edge-01",
        lat=-3.4653,
        lng=-62.2159,
        public_key="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEF",
    )
    assert reg.node_id == "forest-edge-01"


def test_node_registration_rejects_invalid_id():
    with pytest.raises(ValidationError):
        NodeRegistration(
            node_id="bad id!",
            lat=0.0,
            lng=0.0,
            public_key="x" * 32,
        )


def test_generate_node_token():
    raw, token_hash, prefix = generate_node_token()
    assert raw.startswith("sn_")
    assert len(token_hash) == 64
    assert raw.startswith(prefix)
    assert hash_node_token(raw) == token_hash


def test_topic_helpers():
    assert topic_for_node("node-1") == "starscream/nodes/node-1/events"
    assert parse_topic("starscream/nodes/node-1/events") == "node-1"
    assert parse_topic("other/topic") is None


def test_parse_mqtt_payload_with_audio_url():
    payload = parse_mqtt_payload(
        {
            "node_id": "node-1",
            "recorded_at": "2026-06-10T12:00:00Z",
            "audio_url": "https://example.com/chunk.wav",
        }
    )
    assert payload.node_id == "node-1"
    assert payload.audio_url.endswith(".wav")
    assert payload.taxonomy_code == "NATURAL.FOREST"


def test_parse_mqtt_payload_with_base64():
    audio_b64 = base64.b64encode(_make_wav_bytes()).decode()
    payload = parse_mqtt_payload(
        {
            "node_id": "node-1",
            "recorded_at": "2026-06-10T12:00:00Z",
            "audio_base64": audio_b64,
            "taxonomy_code": "WILDLIFE.BIRD",
        }
    )
    assert payload.audio_base64 == audio_b64
    assert payload.taxonomy_code == "WILDLIFE.BIRD"


def test_parse_mqtt_payload_requires_audio():
    with pytest.raises(ValueError, match="audio_url or audio_base64"):
        parse_mqtt_payload(
            {
                "node_id": "node-1",
                "recorded_at": "2026-06-10T12:00:00Z",
            }
        )


def test_decode_audio_base64():
    raw = _make_wav_bytes()
    decoded = decode_audio_base64(base64.b64encode(raw).decode())
    assert decoded == raw


def test_register_sensor_node():
    db = MagicMock()
    db.get.return_value = None
    registration = NodeRegistration(
        node_id="test-node",
        lat=40.0,
        lng=-73.0,
        public_key="-----BEGIN PUBLIC KEY-----\nABC",
    )
    node, token = register_sensor_node(db, registration)
    assert node.node_id == "test-node"
    assert token.startswith("sn_")
    db.add.assert_called_once()


def test_register_sensor_node_duplicate():
    db = MagicMock()
    db.get.return_value = MagicMock()
    registration = NodeRegistration(
        node_id="test-node",
        lat=40.0,
        lng=-73.0,
        public_key="-----BEGIN PUBLIC KEY-----\nABC",
    )
    with pytest.raises(ValueError, match="already registered"):
        register_sensor_node(db, registration)


def test_sensor_register_endpoint():
    from starscream.api.main import app

    mock_db = MagicMock()
    mock_node = MagicMock()
    mock_node.node_id = "api-node"
    mock_node.lat = 51.5
    mock_node.lng = -0.1

    with patch("starscream.api.routes.sensor.register_sensor_node", return_value=(mock_node, "sn_testtoken")):
        from starscream.db.session import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/v1/sensor/register",
                json={
                    "node_id": "api-node",
                    "lat": 51.5,
                    "lng": -0.1,
                    "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEF",
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["node_id"] == "api-node"
    assert body["node_token"] == "sn_testtoken"
    assert body["mqtt_topic"] == "starscream/nodes/api-node/events"


def test_sensor_ingest_requires_auth():
    from starscream.api.main import app

    client = TestClient(app)
    event = {
        "node_id": "node-1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "audio_base64": base64.b64encode(_make_wav_bytes()).decode(),
    }
    response = client.post(
        "/v1/sensor/ingest",
        data={"event_json": json.dumps(event)},
    )
    assert response.status_code == 401
    assert "node token" in response.json()["detail"].lower()


def test_openapi_includes_sensor_endpoints():
    from starscream.api.main import app

    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/sensor/register" in paths
    assert "/v1/sensor/ingest" in paths


def test_sensor_ingest_with_node_token():
    from starscream.api.main import app
    from starscream.db.models import SensorNode

    recording_id = uuid4()
    mock_recording = MagicMock()
    mock_recording.id = recording_id
    mock_recording.spectral_hash = "abc123"

    mock_node = SensorNode(
        node_id="ingest-node",
        lat=40.0,
        lng=-73.0,
        location=None,
        public_key="key",
        token_hash="hash",
        token_prefix="sn_ingest",
    )

    mock_db = MagicMock()

    event = {
        "node_id": "ingest-node",
        "recorded_at": "2026-06-10T12:00:00Z",
        "audio_base64": base64.b64encode(_make_wav_bytes()).decode(),
    }

    with (
        patch("starscream.api.middleware.lookup_sensor_node", return_value=mock_node),
        patch("starscream.api.routes.sensor.submit_sensor_event", return_value=mock_recording),
        patch("starscream.api.routes.sensor.resolve_audio_bytes", return_value=_make_wav_bytes()),
    ):
        from starscream.db.session import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/v1/sensor/ingest",
                headers={"X-Node-Token": "sn_validtoken"},
                data={"event_json": json.dumps(event)},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["recording_id"] == str(recording_id)
    assert body["node_id"] == "ingest-node"
    assert body["spectral_hash"] == "abc123"
