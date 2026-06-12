# Resource guide — what to run where

Starscream work splits into **light** (safe on a busy dev machine) and **heavy** (run on a dedicated terminal, server, or overnight job).

## Light — safe on a busy dev machine

| Work | Examples | Typical load |
|------|----------|--------------|
| Code + docs | importers, API routes, migrations, runbooks | CPU/RAM negligible |
| Unit tests (no Docker) | `pytest --ignore=tests/test_e2e.py --ignore=tests/test_e2e_export.py` | Low |
| Lint | `python -m ruff check .` | Low |
| Metadata-only harvest | `--no-download`, small `--pages` | Network + DB; no librosa/S3 audio |
| Export from existing DB | `starscream-export run ./out --format jsonl --no-audio` | DB read only |

## Heavy — avoid on a maxed-out machine

| Work | Why |
|------|-----|
| `docker compose up` + full stack | Postgres, Meili, MinIO RAM |
| `scripts/smoke_e2e.ps1` | Spins containers + upload pipeline |
| Harvest with audio download | librosa, S3 puts, enrichment HTTP |
| Large `harvest_all --pages 100+` | Network + CPU + disk |
| `pip install -e ".[ml]"` / classification | TensorFlow RAM |
| Parquet/HF export with audio | Reads all FLAC from S3 |

## Recommended split

| Machine | Owns |
|---------|------|
| **Dev laptop** | Importers, schema, docs, small tests |
| **Dedicated workstation** | `docker compose up`, smoke E2E, harvest profiles |
| **Overnight / server** | Large harvest, full export with audio |

## Environment flags for low-memory harvest

Set in `.env` before bulk ingest on a constrained machine:

```env
ENRICH_GEOCODE=false
ENRICH_HABITAT=false
ENRICH_WEATHER=false
ENRICH_OSM=false
```

Use harvest profiles in `config/harvest_profiles.json` — start with `metadata_light`, scale up on another machine.

## Phase priority

- **Phase 1 extras** (Docker extras matrix, MQTT mock test) can wait until someone actually needs them.
- **Phase 2+** is the product: harvest, import, export. Run heavy steps on a workstation; keep day-to-day edits light.

See [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md) for copy-paste commands.
