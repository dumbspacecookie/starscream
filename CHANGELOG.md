# Changelog

All notable changes to Starscream are documented here.

## [Unreleased]

### Added
- Peer-review flag abuse caps (duplicate flag → 409; daily quotas → 429)
- Redis pipeline job queue (`REDIS_URL`) for multi-worker async uploads

## [0.1.0] — 2026-06-10

### Added
- v0.1 scope document (`docs/V0.1_SCOPE.md`) separating core vs experimental features
- MIT code license and `docs/DATA_LICENSE.md` for contributed audio
- GitHub Actions CI: ruff, unit tests, Docker integration test
- End-to-end integration test (`tests/test_e2e.py`) against real Postgres+PostGIS, Meilisearch, MinIO
- Docker entrypoint: automatic `alembic upgrade head` + seed on startup
- Federation harvest retry/backoff with per-page error isolation
- Background job worker for async federation harvest (`POST .../harvest/{slug}?background=true`)
- MQTT subscriber process (`python -m starscream.sensor.mqtt_subscriber`)
- Pipeline failure metrics (`starscream.pipeline.metrics`)
- S3-backed `storage_flac_gb` stat

### Fixed
- Upload routes no longer block the async event loop (sync handlers run in threadpool)
- Rate limiter prunes idle client entries to prevent unbounded memory growth
- Peer review rate/flag endpoints require contributor or admin API key
- `X-Forwarded-For` only trusted when `API_TRUST_PROXY_HEADERS=true`
- Production compose requires explicit secrets (no default passwords)
- `fingerprint.py` fallback guard when audio bytes are unavailable

### Changed
- `[ml]` extra requires Python 3.11–3.12 (TensorFlow wheel availability)
- NOAA/NASA documented as seed catalogs, not live federation
- CORS origins configurable via `CORS_ORIGINS` (default `*` for dev)
