# Starscream roadmap

Prioritized path from a **shippable v0.1** to a more robust platform.  
Focus: green CI, clean git tree, and a validated metadata catalog (Phase 2).

**Resource tiers:** [RESOURCE_GUIDE.md](./RESOURCE_GUIDE.md) · **Runbook:** [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md) · **Scope:** [V0.1_SCOPE.md](./V0.1_SCOPE.md)

---

## How to read this doc

| Tier | Meaning | When |
|------|---------|------|
| **0** | Blocking — repo/CI/corpus truth | Before v0.1 tag |
| **1** | Platform robustness (core path) | v0.1 hardening |
| **2** | Test pyramid expansion | Parallel with Tier 1 |
| **3** | Live federation collectors | After Tier 0 proof |
| **4** | Static dataset importers | After metadata harvest |
| **5** | Service integrations | As multi-worker deploy needs |
| **6** | Data model / scale | When corpus > ~100k rows |
| **7** | Catalog product | Phase 2 (catalog build) |
| **8** | Process & governance | Ongoing |

GitHub issues are filed per tier: labels `tier-0` … `tier-8`, milestone **v0.1** (Tiers 0–2, 7) and **v0.2** (Tiers 3–6 expansion).

---

## Tier 0 — Must happen before “done”

| ID | Item | Owner hint |
|----|------|------------|
| 0.1 | Commit untracked core (`auth`, `middleware`, `peer_review`, admin/contributors/reviews routes, `jobs/`, `inaturalist`, `explore.html`, migrations, tests) | git |
| 0.2 | Push branch + confirm CI **integration** job green on GitHub (testcontainers) | CI |
| 0.3 | Witness run: `docker compose up` → migrations → seed → `scripts/smoke_e2e.ps1` | heavy terminal |
| 0.4 | Freeze v0.1 scope — no new experimental surface until Tier 0 complete | docs |
| 0.5 | Corpus proof: metadata harvest → static import → JSONL export → `validate_export_sample.py` | [PHASE2_RUNBOOK](./PHASE2_RUNBOOK.md) |

**Exit criteria:** Clean `git status`, green integration CI, one validated export artifact.

---

## Tier 1 — Platform robustness

### Reliability & ops

| ID | Item |
|----|------|
| 1.1 | Prod compose smoke in CI (`docker-compose.prod.yml` + health + one upload) |
| 1.2 | Verify entrypoint runs migrations + seed on prod image boot |
| 1.3 | Redis upload job E2E (`?async=true` → poll job → recording in DB + S3) |
| 1.4 | Harvest run alerting — failed runs, partial pages, retry exhaustion in `detail` |
| 1.5 | Connection timeouts on all scripts touching Postgres/Redis/S3 |
| 1.6 | Graceful degradation matrix (no Redis / Meili / enrichment / Freesound key) — doc + tests |
| 1.7 | Backup/restore runbook (Postgres + MinIO) |

### Security & abuse

| ID | Item |
|----|------|
| 1.8 | Auth integration tests (register, upload, admin, peer-review limits) |
| 1.9 | Rate limit E2E with real Redis in integration job |
| 1.10 | Upload hardening regression tests (CORS, size, MIME) |
| 1.11 | Secrets hygiene audit — logs, `.env.example` completeness |

### Data integrity

| ID | Item |
|----|------|
| 1.12 | Dedup E2E variants (cross-source, pointer-only, re-ingest same `external_id`) |
| 1.13 | Meilisearch reindex job after bulk harvest/import |
| 1.14 | Alembic migration discipline — no forked heads; all versions committed |
| 1.15 | License audit — CC-BY-NC never stores audio bytes (every connector path) |

---

## Tier 2 — Test pyramid

### Integration / E2E (highest ROI first)

| ID | Target | Assert |
|----|--------|--------|
| 2.1 | Federation harvest E2E | HTTP fixtures → Postgres → searchable |
| 2.2 | FSD50K/ESC-50 import E2E | CSV → DB → export row grounding + `world_model_labels` |
| 2.3 | Export E2E | `test_e2e_export.py` green — JSONL matches DB |
| 2.4 | Background upload job E2E | Redis queue → worker → completed status |
| 2.5 | Spatial + filter combos | `near=` + taxonomy + license |
| 2.6 | Harvest scheduler | scheduled run → `HarvestRun` + `detail` JSON |
| 2.7 | Peer review flow E2E | flag → limits → admin metrics |
| 2.8 | MQTT ingest E2E | testcontainers Mosquitto or mock broker |
| 2.9 | GraphQL smoke | query against real DB (if kept in scope) |
| 2.10 | Chaos tests | Meili down, S3 timeout, harvest page 500 → run continues |

### CI hardening

| ID | Item |
|----|------|
| 2.11 | Integration job runs `test_e2e_export.py` |
| 2.12 | Pin testcontainer image digests |
| 2.13 | Coverage floor on ingest, dedup, export, harvest |
| 2.14 | Nightly harvest profile workflow (dedicated runner, not PR CI) |

---

## Tier 3 — Live federation collectors

### Existing (prove at scale first)

| Slug | Notes |
|------|-------|
| `freesound` | API key; OAuth for full quality (planned) |
| `xeno-canto` | CC-BY-NC → pointer-only |
| `inaturalist` | Rate limits + pagination |
| `internet-archive` | Mixed licenses |
| `noaa` / `nasa` | Seed catalogs (~40 files each) |

| ID | Item |
|----|------|
| 3.1 | Run all connectors via `metadata_light` harvest profile |
| 3.2 | Per-connector harvest metrics in admin API |
| 3.3 | Incremental harvest checkpoints per source |
| 3.4 | Freesound OAuth for full-quality audio |
| 3.5 | iNaturalist backoff + pagination caps |

### New collectors (v0.2+ — one at a time)

Each new source requires: connector + seed + harvest profile + grounding + license policy + fixture integration test.

| Source | Value |
|--------|-------|
| Macaulay Library (Cornell) | Bioacoustics |
| Wikimedia Commons | CC ambient/human |
| Zenodo/Figshare DOI harvester | Generic datasets |
| GBIF media links | Metadata pointers |
| OpenSLR / Common Voice | Speech |

---

## Tier 4 — Static importers

### Done

- FSD50K (`starscream-import fsd50k`)
- ESC-50 (`starscream-import esc50`)

### Infrastructure (build once)

| ID | Item |
|----|------|
| 4.1 | Generic manifest importer (JSONL/CSV schema) |
| 4.2 | Import validation CLI (license + path pre-flight) |
| 4.3 | Batch re-ingest (update grounding without duplicates) |
| 4.4 | Per-dataset audio policy (copy / pointer / transcode) |

### Candidate datasets (v0.2+)

UrbanSound8K, NSynth, BirdCLEF/DCASE sets, AudioSet metadata (pointer-only), WavCaps/Clotho (captions).

---

## Tier 5 — Service integrations

| Service | Today | Target |
|---------|-------|--------|
| Postgres + PostGIS | Core | Pool tuning; partitions at 10M+ rows |
| MinIO / S3 | Core | Lifecycle, multipart, checksums, mirror failover tests |
| Meilisearch | Core | Reindex job, index versioning |
| Redis | Optional | **Required** for multi-worker prod |
| MQTT | Wired, unproven | Broker in compose + subscriber E2E |
| Hugging Face | `export publish` | Publish E2E with test repo |
| GraphQL | Experimental | Cut or commit with e2e |
| BitTorrent | Experimental | Cut or one e2e |
| WebSocket stream | Present | Load + reconnect tests |
| Enrichment APIs | OSM/weather/geocode | Circuit breaker + cache + metrics |
| ML `[ml]` | Optional | ONNX for 3.13+ |
| Observability | Admin metrics | OpenTelemetry + Prometheus dashboards |

**Do not add a second primary database until Tier 0–7 are green.**

---

## Tier 6 — Data model & scale (corpus > ~100k)

| ID | Item |
|----|------|
| 6.1 | Taxonomy normalization table |
| 6.2 | Annotation / event layer (segments, fold labels) |
| 6.3 | Provenance graph (source → harvest_run → recording) |
| 6.4 | Quality/trust scores (`004_quality_trust` migration wired) |
| 6.5 | Postgres full-text fallback when Meili down |
| 6.6 | Cold archival tier for FLAC |
| 6.7 | Analytics DB (ClickHouse/BQ) — scale only |
| 6.8 | Vector index for similar sounds — post-v0.1 |

---

## Tier 7 — Catalog product

| ID | Item | Status |
|----|------|--------|
| 7.1 | `metadata_light` harvest | pending |
| 7.2 | FSD50K + ESC-50 import | pending |
| 7.3 | Overnight audio harvest (`catalog_build`) | pending |
| 7.4 | JSONL export + `validate_export_sample.py` | pending |
| 7.5 | Export schema semver in `export_meta.json` | pending |
| 7.6 | Training license filters documented | partial — [TRAINING_EXPORT.md](./TRAINING_EXPORT.md) |
| 7.7 | Richer `world_model_labels` for top taxonomies | partial — minimal heuristics |
| 7.8 | Public sample corpus tarball (CC0/CC-BY) | pending |

---

## Tier 8 — Process & governance

| ID | Item |
|----|------|
| 8.1 | PR = vertical slice (code + tests + migration + docs, all committed) |
| 8.2 | Connector definition-of-done checklist in [FEDERATION.md](./FEDERATION.md) |
| 8.3 | CHANGELOG + semver; tag v0.1 only after Tier 0 |
| 8.4 | CI matrix Python 3.11 + 3.12 |
| 8.5 | Enforce [RESOURCE_GUIDE](./RESOURCE_GUIDE.md) — heavy work on dedicated machines |
| 8.6 | Backlog sync — [BACKLOG.md](./BACKLOG.md) ↔ this roadmap |

---

## Suggested execution order

```
Week A — Trust (Tier 0)
  0.1 → 0.2 → 0.3 → 0.4

Week B — Product proof (Tier 7 + Tier 2.2–2.3)
  7.1 → 7.2 → 7.4 → export E2E in CI

Week C — Robustness depth (Tier 1 + Tier 2)
  1.3 Redis job E2E, 2.1 harvest E2E, 1.13 Meili reindex, 3.3 checkpoints

Week D — Expand (one slice only)
  One new collector OR one new importer — full vertical slice + test
```

---

## Anti-goals (defer)

- Celery/RQ / multi-region HA
- GraphQL + BitTorrent + MQTT + ML + many new collectors in one sprint
- Second primary database before corpus proof
- AudioSet YouTube download at scale
- Chasing “production-grade everything” before green integration CI and a clean git tree

---

## Related docs

- [BACKLOG.md](./BACKLOG.md) — short status tracker
- [TRAINING_EXPORT.md](./TRAINING_EXPORT.md) — training export guide
- [IMPORTERS.md](./IMPORTERS.md) — static datasets
- [CHANGELOG.md](../CHANGELOG.md) — release notes
