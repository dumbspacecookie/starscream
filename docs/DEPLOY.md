# Production deployment

Deploy Starscream as a Docker Compose stack with Postgres (PostGIS), Meilisearch, MinIO, and the API. MQTT is optional for IoT sensor nodes.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- At least 4 GB RAM for the full stack (Meilisearch + audio pipeline)

## Quick start

```bash
# Copy and set required secrets (no insecure defaults in prod compose)
cp .env.prod.example .env
# Edit .env — POSTGRES_PASSWORD, MEILISEARCH_API_KEY, MINIO_ROOT_USER,
# MINIO_ROOT_PASSWORD, and ADMIN_API_KEY are all required.

# Fail fast if any required variable is missing
python scripts/validate_env.py

# Build and start core services (entrypoint runs migrations + seed automatically)
docker compose -f docker-compose.prod.yml up -d --build

# Verify health
curl -s http://localhost:8000/health | jq
python scripts/healthcheck.py
```

API docs: http://localhost:8000/docs

## Services

| Service | Image / build | Purpose |
|---------|---------------|---------|
| `api` | Built from `Dockerfile` | FastAPI application on port 8000 |
| `postgres` | `postgis/postgis:16-3.4` | Primary database with PostGIS |
| `meilisearch` | `getmeili/meilisearch:v1.11` | Full-text search index |
| `minio` | `minio/minio` | S3-compatible object storage for audio |
| `mqtt` | `eclipse-mosquitto:2` | Optional broker for sensor nodes (profile `mqtt`) |
| `redis` | `redis:7-alpine` | Optional shared rate-limit store (profile `redis`) |

## Environment variables

Set these in `.env` or export before `docker compose up`:

| Variable | Default | Used by |
|----------|---------|---------|
| `POSTGRES_PASSWORD` | `starscream` | Postgres + API `DATABASE_URL` |
| `MEILISEARCH_API_KEY` | (empty) | Meilisearch master key + API client |
| `MINIO_ROOT_USER` | `starscream` | MinIO + API `S3_ACCESS_KEY` |
| `MINIO_ROOT_PASSWORD` | `starscream` | MinIO + API `S3_SECRET_KEY` |
| `S3_BUCKET` | `starscream-audio` | API object storage bucket |
| `ADMIN_API_KEY` | (empty) | Admin routes |
| `API_RATE_LIMIT_PER_MIN` | `1000` | Rate limit middleware |
| `REDIS_URL` | (empty) | Redis-backed rate limiter (e.g. `redis://redis:6379/0`) |

When `MEILISEARCH_API_KEY` is set, Meilisearch runs with `MEILI_MASTER_KEY` and the API sends the same key on search requests.

### Validate environment before deploy

`scripts/validate_env.py` reads required keys from `.env.prod.example` (everything above the `# Optional` section) and checks that each is set in `.env` and/or the process environment:

```bash
python scripts/validate_env.py              # default: repo-root .env
python scripts/validate_env.py --env-file /path/to/.env
```

Exit **0** when all required variables are present; exit **1** with a list of missing keys otherwise. Run this in CI or before `docker compose up` to catch incomplete secrets early.

## Health checks

**HTTP endpoint** — `GET /health` returns dependency status:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "dependencies": {
    "postgres": {"ok": true, "detail": "connected"},
    "meilisearch": {"ok": true, "detail": "available"},
    "minio": {"ok": true, "detail": "bucket 'starscream-audio' reachable"}
  }
}
```

Returns HTTP **503** with `"status": "degraded"` when any dependency is unreachable.

**CLI probe** — used by Docker healthchecks and load balancers:

```bash
python scripts/healthcheck.py   # exit 0 = healthy, exit 1 = unhealthy
```

Both use the shared logic in `starscream.health.check_dependencies`.

## Optional Redis (distributed rate limiting)

By default the API rate limiter uses an in-memory sliding window per process. For multiple API replicas, enable Redis so all workers share one counter per client IP:

```bash
# In .env
REDIS_URL=redis://redis:6379/0

docker compose -f docker-compose.prod.yml --profile redis up -d
```

Install the optional Python dependency when running the API outside Docker: `pip install -e ".[redis]"`.

When `REDIS_URL` is unset, behavior is unchanged (in-memory limiter).

## Reverse proxy and TLS (nginx)

`deploy/nginx.conf` terminates HTTP on port 80 and proxies to uvicorn on `127.0.0.1:8000`. It sets security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, etc.) and forwards `X-Forwarded-For` / `X-Forwarded-Proto` so the API can honor `API_TRUST_PROXY_HEADERS=true` behind the proxy.

**TLS setup:**

1. Copy or symlink the config: `sudo cp deploy/nginx.conf /etc/nginx/sites-available/starscream`
2. Obtain certificates (Let's Encrypt example): `sudo certbot certonly --nginx -d starscream.example`
3. Uncomment the `listen 443 ssl` server block and `ssl_certificate` paths in `deploy/nginx.conf`
4. Uncomment the HTTP→HTTPS redirect (`return 301 https://$host$request_uri;`) in the port-80 server block
5. Reload nginx: `sudo nginx -t && sudo systemctl reload nginx`

Set `API_TRUST_PROXY_HEADERS=true` in `.env` when the API sits behind nginx so rate limits and logs use the real client IP from `X-Forwarded-For`.

## Optional MQTT (IoT sensors)

Enable the Mosquitto broker for sensor node ingest:

```bash
docker compose -f docker-compose.prod.yml --profile mqtt up -d
```

Broker listens on port **1883** with anonymous publish/subscribe (development-friendly). Harden `deploy/mosquitto.conf` with TLS and ACLs before exposing publicly. See [SENSOR.md](./SENSOR.md) for topic layout.

## Operations

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f api

# Restart API after config change
docker compose -f docker-compose.prod.yml up -d --build api

# Stop stack (data volumes preserved)
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (destructive)
docker compose -f docker-compose.prod.yml down -v
```

## Development vs production

| | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|--|---------------------------|----------------------------------|
| API | Run locally with `uvicorn` | Containerized |
| Postgres ports | Exposed `5432` | Internal only |
| Meilisearch | `MEILI_ENV=development` | `MEILI_ENV=production` |
| Healthchecks | Postgres only | All services + API |
| Restart policy | None | `unless-stopped` |

For local development, keep using `docker compose up -d` (dev file) plus `uvicorn starscream.api.main:app --reload`.

## MinIO bucket bootstrap

The API creates the audio bucket on first upload via `starscream.storage.ensure_bucket`. If health checks fail on a fresh MinIO instance because the bucket does not exist yet, create it once:

```bash
docker compose -f docker-compose.prod.yml run --rm api python -c \
  "from starscream.storage import ensure_bucket; ensure_bucket()"
```

After that, `/health` and `scripts/healthcheck.py` should report MinIO as healthy.

## Real-time ingest stream (WebSocket)

Clients can subscribe to new recording ingest events on **`WS /v1/stream/ingest`**.

**Filters** (query string or first JSON message after connect):

| Parameter | Description |
|-----------|-------------|
| `taxonomy` / `taxonomy_prefix` | Only events whose `taxonomy_code` starts with this prefix |
| `lat`, `lng`, `radius_km` | Geographic filter (haversine, km) — all three required |

Example:

```bash
# All ingests
wscat -c ws://localhost:8000/v1/stream/ingest

# Birds near NYC within 25 km
wscat -c 'ws://localhost:8000/v1/stream/ingest?taxonomy=WILDLIFE&lat=40.758&lng=-73.985&radius_km=25'
```

Event payload:

```json
{
  "type": "ingest",
  "recording": {
    "id": "...",
    "taxonomy_code": "WILDLIFE.BIRD",
    "location": {"lat": 40.758, "lng": -73.985},
    "recorded_at": "2024-06-15T10:00:00+00:00",
    "title": "Robin song"
  }
}
```

**Debug UI:** open http://localhost:8000/stream while running the API locally.

**Development:** events use an in-process pub/sub (`starscream.events.IngestBroadcaster`) wired from `contrib/submit.py` and `federation/ingest.py`.

**Production:** run a single API replica or replace the broadcaster with **Redis pub/sub** (e.g. `PUBLISH starscream:ingest <json>`) so all workers and regions receive ingest notifications. The in-memory singleton does not propagate across multiple Uvicorn workers or containers.
