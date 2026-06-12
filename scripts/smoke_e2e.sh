#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting dev compose stack..."
docker compose up -d

export ENRICH_GEOCODE=false
export ENRICH_HABITAT=false
export ENRICH_WEATHER=false
export ENRICH_OSM=false

echo "Waiting for Postgres, Meilisearch, and MinIO..."
for i in $(seq 1 60); do
  if python scripts/healthcheck.py; then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Timed out waiting for dependency health checks" >&2
    exit 1
  fi
  sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Seeding taxonomy, sources, bucket, and search index..."
python -m starscream.seed

echo "Running E2E integration tests..."
STARSCREAM_E2E_COMPOSE=1 python -m pytest tests/test_e2e.py -m integration -v
