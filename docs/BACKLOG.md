# Starscream v0.1 — remaining backlog

Last updated: lightweight-first execution (Phase 2 on dedicated terminals).

## Resource tiers

| Tier | Run where | Examples |
|------|-----------|----------|
| **Light** | Dev laptop | Code, docs, unit tests, importers (parse only) |
| **Heavy** | Dedicated terminal / overnight | Docker, E2E, harvest with audio, ML, full export |

See [RESOURCE_GUIDE.md](./RESOURCE_GUIDE.md), [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md), and the full plan [ROADMAP.md](./ROADMAP.md).

GitHub: [SETUP_GITHUB.md](./SETUP_GITHUB.md) — remote, `gh`, issues, PR. Issue bodies: [GITHUB_ISSUES.md](./GITHUB_ISSUES.md).

## P0 — Proof (heavy — defer to dedicated terminal)

| ID | Item | Status |
|----|------|--------|
| P0-1 | Run E2E / smoke against Docker | pending — run elsewhere |
| P0-5 | CI integration green on GitHub | pending |

## Phase 1 — Release polish (skipped for now)

| ID | Item | Status |
|----|------|--------|
| P2-4 | Docker BUILD_EXTRAS | deferred |
| P3-3 | MQTT mock test | deferred |

## Phase 2 — Catalog build (product work)

| ID | Item | Status |
|----|------|--------|
| P2-H1 | Harvest profiles (`config/harvest_profiles.json`) | **done** |
| P2-H2 | `scripts/run_harvest_profile.py` | **done** |
| P2-H3 | FSD50K static importer (`starscream-import fsd50k`) | **done** |
| P2-H4 | Phase 2 runbook | **done** |
| P2-R1 | Run `metadata_light` harvest on dedicated machine | pending |
| P2-R2 | FSD50K import from Zenodo extract | pending |
| P2-R3 | Freesound+iNat audio harvest overnight | pending |
| P2-R4 | JSONL export + row quality review | pending |
| P2-C1 | ESC-50 static importer | **done** |
| P2-C2 | Federated grounding helpers (`federation/grounding.py`) | **done** |
| P2-C3 | Ingest grounding fallback + minimal `world_model_labels` | **done** |
| P2-C4 | Training export guide (`docs/TRAINING_EXPORT.md`) | **done** |
| P2-C5 | Import profiles + `run_import_profile.py` | **done** |
| P2-C6 | `starscream-import list` + `corpus_report.py` | **done** |
| P2-C7 | `validate_export_sample.py` + export/ingest tests | **done** |
| P2-C8 | Taxonomy-aware `world_model_labels` on federated ingest | **done** |

## Done (platform)

P1-* (jobs, redis rate limit, harvest retry, metrics), P3-1/2/4/5, most P2 deploy docs.

## Explicitly deferred

GraphQL/BitTorrent cuts, ONNX ML, Celery/RQ, multi-region HA.
