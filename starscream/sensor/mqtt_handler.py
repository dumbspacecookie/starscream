import base64
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


MQTT_TOPIC_PREFIX = "starscream/nodes"
DEFAULT_TAXONOMY = "NATURAL.FOREST"


class MqttSensorPayload(BaseModel):
    """Parsed MQTT JSON event from a sensor node."""

    node_id: str = Field(..., min_length=1, max_length=64)
    recorded_at: datetime
    audio_url: str | None = None
    audio_base64: str | None = None
    taxonomy_code: str = DEFAULT_TAXONOMY
    title: str | None = None
    description: str | None = None
    duration_s: float | None = None
    sample_rate_hz: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_audio_reference(self) -> "MqttSensorPayload":
        if not self.audio_url and not self.audio_base64:
            raise ValueError("MQTT payload must include audio_url or audio_base64")
        return self


def topic_for_node(node_id: str) -> str:
    return f"{MQTT_TOPIC_PREFIX}/{node_id}/events"


def parse_topic(topic: str) -> str | None:
    """Extract node_id from starscream/nodes/{id}/events."""
    parts = topic.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "starscream" and parts[1] == "nodes" and parts[3] == "events":
        return parts[2]
    return None


def parse_mqtt_payload(data: str | dict[str, Any]) -> MqttSensorPayload:
    """Parse MQTT JSON payload with audio_url or base64 chunk + metadata."""
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid MQTT JSON: {exc}") from exc
    else:
        parsed = data

    if not isinstance(parsed, dict):
        raise ValueError("MQTT payload must be a JSON object")

    return MqttSensorPayload.model_validate(parsed)


def decode_audio_base64(audio_base64: str) -> bytes:
    """Decode base64 audio chunk, tolerating data-URI prefixes."""
    payload = audio_base64.strip()
    if "," in payload and payload.startswith("data:"):
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid audio_base64: {exc}") from exc
