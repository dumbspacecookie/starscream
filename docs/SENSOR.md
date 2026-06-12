# Starscream IoT Sensor Network

Distributed acoustic sensor nodes publish sound events to Starscream via MQTT or HTTP. This document covers the reference hardware, MQTT topic layout, and API endpoints.

## Reference hardware (BOM)

Open-source node design from the Starscream spec (~$45 per node at scale):

| Component | Purpose |
|-----------|---------|
| Raspberry Pi Zero 2W | Edge compute |
| USB omnidirectional microphone | 44.1 kHz / 16-bit minimum; 96 kHz preferred for ultrasonic |
| u-blox NEO-6M GPS module | Precise lat/lng for each event |
| 4G/LTE modem or WiFi | Connectivity to regional MQTT broker |
| Solar panel + 18650 LiPo | Off-grid power |
| IP67 weatherproof enclosure | Pole-mountable outdoor deployment |

**Firmware behavior:**

- Continuous rolling capture with silence-gated segmentation
- Local preprocessing: normalization, spectral fingerprint computation
- MQTT publish to regional broker on sound event detection
- Firmware OTA update via MQTT retained message on `starscream/nodes/{id}/config`

## MQTT topic structure

```
starscream/nodes/{node_id}/events    # sound event JSON (primary ingest)
starscream/nodes/{node_id}/status    # heartbeat, battery, signal (optional)
starscream/nodes/{node_id}/config    # OTA firmware/config (retained)
```

Example event topic: `starscream/nodes/forest-edge-01/events`

### Event payload (JSON)

At least one of `audio_url` or `audio_base64` is required:

```json
{
  "node_id": "forest-edge-01",
  "recorded_at": "2026-06-10T14:32:00Z",
  "audio_url": "https://broker-cache.example/chunks/abc123.wav",
  "taxonomy_code": "NATURAL.FOREST",
  "title": "Dawn chorus segment",
  "duration_s": 4.2,
  "sample_rate_hz": 44100,
  "metadata": {
    "trigger_db": 42,
    "firmware": "1.0.3"
  }
}
```

Alternatively, embed a base64-encoded WAV/FLAC chunk:

```json
{
  "node_id": "forest-edge-01",
  "recorded_at": "2026-06-10T14:32:00Z",
  "audio_base64": "<base64 chunk>",
  "taxonomy_code": "WILDLIFE.BIRD"
}
```

Parse payloads in Python with `starscream.sensor.mqtt_handler.parse_mqtt_payload`.

## HTTP API

### Register a node

```
POST /v1/sensor/register
Content-Type: application/json

{
  "node_id": "forest-edge-01",
  "lat": -3.4653,
  "lng": -62.2159,
  "public_key": "-----BEGIN PUBLIC KEY-----\n..."
}
```

Returns a one-time `node_token` (prefix `sn_`) and the MQTT topic for events. Store the token securely on the device.

### Ingest an event

```
POST /v1/sensor/ingest
X-Node-Token: sn_...
Content-Type: multipart/form-data

event_json: { ... same shape as MQTT payload ... }
audio: (optional WAV/FLAC file if not using audio_url/base64 in JSON)
```

Authentication (either):

- **Node token** — header `X-Node-Token` or `Authorization: Bearer sn_...`
- **Contributor API key** — header `X-API-Key` or `Authorization: Bearer ss_...`

When using a node token, `node_id` in the payload must match the authenticated node.

Response:

```json
{
  "recording_id": "uuid",
  "node_id": "forest-edge-01",
  "spectral_hash": "...",
  "mqtt_topic": "starscream/nodes/forest-edge-01/events"
}
```

## Database

Registered nodes are stored in the `sensor_nodes` table (Alembic revision `010`). Each node has a cryptographic identity (`public_key`), location, and hashed node token.

## Node governance

Anyone can deploy a registered node. Tampered or unreliable nodes can be deactivated (`is_active = false`) by operators. Event counts and `last_seen_at` support anomaly monitoring.

## Related docs

- [starscream-spec.md](../starscream-spec.md) — collection strategy and deployment targets
- [METADATA_SCHEMA.md](METADATA_SCHEMA.md) — `recorder_type: iot` on ingested recordings
