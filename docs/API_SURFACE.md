# Starscream API Surface

Complete reference for every HTTP, GraphQL, and WebSocket endpoint exposed by the Starscream API server (`uvicorn starscream.api.main:app`).

Base URL (local dev): `http://localhost:8000`

All JSON error responses include `request_id` (echoed in `X-Request-Id` header).

---

## Web UI pages

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to `/explore` |
| GET | `/explore` | Full-text search browser |
| GET | `/upload` | Single contribution upload form |
| GET | `/batch` | ZIP batch upload UI |
| GET | `/mobile` | Mobile recorder (offline manifest + sync) |
| GET | `/recording` | Recording detail page (`?id=UUID`) |
| GET | `/stats` | Corpus statistics dashboard |
| GET | `/contributors-page` | Contributor directory |
| GET | `/leaderboard` | Contributor leaderboard |
| GET | `/stream` | Live WebSocket ingest feed demo |
| GET | `/manifest.webmanifest` | PWA manifest |
| GET | `/sw.js` | Service worker |
| GET | `/static/*` | Static assets (CSS, icons) |
| GET | `/docs/{doc_path}` | Serve markdown files from `docs/` |

---

## Operations & auto-docs

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Dependency health (Postgres, Meilisearch, S3); 503 if degraded | — |
| GET | `/docs` | Swagger UI (FastAPI auto-generated) | — |
| GET | `/redoc` | ReDoc API reference | — |
| GET | `/openapi.json` | OpenAPI 3 schema | — |

---

## REST API (`/v1`)

### Recordings

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/recordings` | List recordings with geo/temporal/taxonomy filters and cursor pagination | — |
| GET | `/v1/recordings/{recording_id}` | Get single recording metadata | — |
| GET | `/v1/recordings/{recording_id}/audio.flac` | Stream FLAC audio | — |
| GET | `/v1/recordings/{recording_id}/audio.mp3` | Stream MP3 preview | — |
| GET | `/v1/recordings/{recording_id}/canonical` | Canonical recording and duplicate alternates | — |
| GET | `/v1/recordings/{recording_id}/similar` | Spectrally similar recordings | — |
| GET | `/v1/recordings/{recording_id}/classifications` | BirdNET/YAMNet classification results | — |
| GET | `/v1/recordings/{recording_id}/spectrogram.png` | Spectrogram PNG (generates on first request if missing) | — |
| POST | `/v1/recordings` | Direct multipart ingest (taxonomy, lat/lng, recorded_at, optional audio) | — |

**`GET /v1/recordings` query parameters:** `near` (lat,lng), `radius_km`, `taxonomy`, `recorded_after`, `recorded_before`, `season`, `habitat`, `quality_min`, `tag`, `source_object`, `material`, `environment`, `contributions_only`, `limit`, `cursor`.

**`GET /v1/recordings/{id}/similar` query parameters:** `limit` (1–50, default 10).

### Peer review

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/v1/recordings/{recording_id}/rate` | Rate recording quality (1–5 stars) | — |
| POST | `/v1/recordings/{recording_id}/flag` | Flag recording for admin review | — |

### Contributions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/contrib/guidelines` | Contribution requirements summary | — |
| POST | `/v1/contrib/register` | Register contributor; returns API key | — |
| POST | `/v1/contrib/validate` | Validate manifest + optional audio (multipart) | — |
| POST | `/v1/contrib/upload` | Upload manifest + audio | Contributor API key |
| POST | `/v1/contrib/validate-batch` | Validate ZIP of contribution packages | — |
| POST | `/v1/contrib/upload-batch` | Upload ZIP of valid packages | Contributor API key |
| GET | `/v1/contrib/tags` | List popular tags (`q`, `limit`) | — |

### Search

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/search` | Full-text search via Meilisearch | — |

**Query parameters:** `q`, `limit`, `taxonomy`, `country`, `material`, `is_contribution`.

### Taxonomy

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/taxonomy` | Full taxonomy tree | — |
| GET | `/v1/taxonomy/{code}` | Subtree rooted at code | — |

### Sources

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/sources` | List federation and contribution sources | — |

### Stats

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/stats` | Corpus totals (recordings, countries, contributions, tags) | — |

### Contributors

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/contributors/leaderboard` | Top contributors by sound count (`limit`) | — |
| GET | `/v1/contributors/{contributor_id}` | Contributor profile | — |

### Federation

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/v1/federation/harvest/{source_slug}` | Trigger harvest for one source | — |

**Source slugs:** `freesound`, `xeno-canto`, `inaturalist`, `internet-archive`, `noaa`, `nasa`.

**Query parameters:** `pages`, `page_size`, `download_previews`.

### Sensor (IoT)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/v1/sensor/register` | Register sensor node; returns node token + MQTT topic | — |
| POST | `/v1/sensor/ingest` | Ingest sensor event + optional audio (multipart) | `X-Node-Token` or contributor API key |

### Admin

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/admin/flags` | Flag review queue (`status`, `limit`, `offset`) | `ADMIN_API_KEY` |
| GET | `/v1/admin/harvest-runs` | Recent federation harvest run history | `ADMIN_API_KEY` |

### Governance

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v1/governance` | JSON summary of Foundation policies (rate tiers, attribution) | — |

---

## GraphQL

Requires `pip install -e ".[graphql]"`.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/v1/graphql` | GraphQL API (no IDE) | — |
| POST | `/graphql` | GraphQL API with Strawberry IDE | — |

### Queries

| Field | Arguments | Returns |
|-------|-----------|---------|
| `recordings` | `near`, `taxonomy`, `season`, `qualityMin`, `limit` | `[RecordingType]` — spatial/temporal listing |
| `recording` | `id` | `RecordingType` or null |
| `search` | `q`, `limit` | `SearchResult` — Meilisearch hits |
| `stats` | — | `Stats` — corpus totals |

Example:

```graphql
query {
  recordings(near: "37.77,-122.42", taxonomy: "WILDLIFE", limit: 10) {
    id
    title
    sourceObject
    location { lat lng }
  }
}
```

---

## WebSocket

| Protocol | Path | Description | Auth |
|----------|------|-------------|------|
| WS | `/v1/stream/ingest` | Real-time ingest event stream | — |

**Connection:** `ws://localhost:8000/v1/stream/ingest`

**Optional filter** (query string or first JSON message within 2s):

| Parameter | Description |
|-----------|-------------|
| `taxonomy` / `taxonomy_prefix` | Filter by taxonomy code prefix |
| `lat`, `lng` | Center point for geo filter |
| `radius_km` / `radius` | Radius in km (default 50 when lat/lng set) |

**Server messages:**

```json
{"type": "subscribed", "filter": {"taxonomy_prefix": "WILDLIFE", ...}}
{"type": "ingest", "recording": {"id": "...", "title": "...", ...}}
```

---

## Authentication headers

| Header | Used for |
|--------|----------|
| `X-API-Key` | Contributor API key (`ss_...`) or admin key |
| `Authorization: Bearer <key>` | Alternative to `X-API-Key` |
| `X-Node-Token` | Sensor node token (`sn_...`) |
| `X-Request-Id` | Optional client-provided request ID (echoed in response) |

---

## Rate limiting

All endpoints are subject to per-IP sliding-window rate limiting (default 1000 requests/minute, configurable via `API_RATE_LIMIT_PER_MIN`).

| Status | Meaning |
|--------|---------|
| 429 | Rate limit exceeded; `Retry-After: 60` |

Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`.

---

## Related

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system design and data flow
- [CONTRIBUTING.md](./CONTRIBUTING.md) — manifest schema and upload workflow
- [GOVERNANCE.md](./GOVERNANCE.md) — API tiers and attribution policy
