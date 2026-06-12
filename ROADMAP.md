# Starscream roadmap (phases)

High-level phase checklist. For prioritized tiers and GitHub issue mapping, see [docs/ROADMAP.md](./docs/ROADMAP.md).

Maintained by **dumbspacecookie**.

## Phase 1 — Core corpus UX & ops ✅

- [x] Web upload form (`/upload`) with manifest validation
- [x] Explore browser (`/explore`) with full-text search
- [x] Similar-sounds dedup hint on upload
- [x] Shared nav + Community dropdown
- [x] Recording detail page (`/recording?id=UUID`)
- [x] Stats dashboard (`/stats`)
- [x] Dataset export + HF publish + torrent
- [x] Federation: Freesound, Xeno-canto, iNaturalist
- [x] Batch harvest scheduler
- [x] Full processing pipeline

## Phase 2 — Scene graph & cross-modal grounding ✅

- [x] Scene graph schema + API
- [x] Cross-modal enrichment (geocode, habitat, weather, OSM)
- [x] World-model label heuristics on ingest
- [x] Quality/trust migration (`004_quality_trust`)

## Phase 3 — Community & governance ✅

- [x] Contributor accounts + API keys
- [x] Peer review flags
- [x] Admin harvest controls
- [x] Governance docs + model card template

## Phase 4 — Catalog consumer layer ✅

- [x] Committed `corpus/dataset.jsonl` (metadata-only)
- [x] Offline catalog CLI (`starscream.catalog`)
- [x] MCP server for search tools
- [x] Redistribution + training export docs

## Next

See [docs/BACKLOG.md](./docs/BACKLOG.md) and [docs/PHASE2_RUNBOOK.md](./docs/PHASE2_RUNBOOK.md) for harvest scale-up and release tasks.
