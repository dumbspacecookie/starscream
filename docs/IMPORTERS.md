# Static dataset importers

Import research datasets from **local files** into Starscream (no live API). Run on a machine with the dataset already downloaded.

## Prerequisites

```bash
alembic upgrade head
python -m starscream.seed   # registers fsd50k + esc50 sources
```

For bulk import, disable enrichment HTTP in `.env`:

```env
ENRICH_GEOCODE=false
ENRICH_HABITAT=false
ENRICH_WEATHER=false
ENRICH_OSM=false
```

## FSD50K

Download from [Zenodo](https://zenodo.org/records/4060432).

```bash
# Metadata only (light)
starscream-import fsd50k /data/FSD50K/FSD50K.metadata/dev.csv --split dev --limit 500 --no-audio

# With local audio copy (heavy — librosa + S3)
starscream-import fsd50k /data/FSD50K/FSD50K.metadata/dev.csv \
  --audio-dir /data/FSD50K/FSD50K.dev_audio --split dev --limit 1000
```

License: per-clip Freesound (importer defaults CC-BY). Rows get `source_object` / `source_action` via `federation/grounding.py`.

## ESC-50

Clone or download [ESC-50](https://github.com/karolpiczak/ESC-50).

```bash
# Metadata index (CC-BY-NC → pointer-only in Starscream; no local audio stored)
starscream-import esc50 /data/ESC-50/meta/esc50.csv --no-audio

# With audio dir (still pointer-only for NC license)
starscream-import esc50 /data/ESC-50/meta/esc50.csv --audio-dir /data/ESC-50/audio
```

## Import profiles

Named batches in `config/import_profiles.json` (mirror harvest profiles):

```bash
starscream-import list
python scripts/run_import_profile.py --list
python scripts/run_import_profile.py fsd50k_dev_sample --dry-run
```

Edit CSV paths (`CHANGE_ME/...`) before running on your data machine.

## After import

```bash
python scripts/corpus_report.py
curl http://localhost:8000/v1/stats
starscream-export run ./corpus/ --format jsonl --no-audio
```

Training export: [TRAINING_EXPORT.md](./TRAINING_EXPORT.md)

## vs federation harvest

| Path | Use when |
|------|----------|
| `starscream-harvest` | Live APIs (Freesound, iNaturalist, …) |
| `starscream-import` | Static tarballs/CSVs already on disk |

See [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md) for harvest profiles.
