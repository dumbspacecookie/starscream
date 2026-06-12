# Phase 2 runbook — catalog build (run on a dedicated machine)

Copy-paste commands for growing the Starscream corpus. Run on a machine with enough RAM and disk — not a cramped laptop with Docker already maxed out.

## 0. One-time stack (heavy)

```powershell
cd /path/to/starscream
docker compose up -d
pip install -e ".[dev,export]"
cp .env.example .env
# Add FREESOUND_API_KEY for Freesound harvest

alembic upgrade head
python -m starscream.seed
```

Optional smoke (heavy):

```powershell
.\scripts\smoke_e2e.ps1
```

## 1. Metadata-only crawl (default — `CATALOG_ONLY=true`)

Indexes external catalogs without downloading audio — the default posture for git + license safety:

```powershell
# Low memory profile (see config/harvest_profiles.json)
python scripts/run_harvest_profile.py metadata_light

# Or manual:
python -m starscream.jobs.harvest_all `
  --sources inaturalist,xeno-canto,internet-archive `
  --pages 20 --page-size 50 --no-download
```

Freesound still needs `FREESOUND_API_KEY`:

```powershell
python -m starscream.jobs.harvest_all --sources freesound --pages 10 --page-size 50 --no-download
```

## 2. Audio download harvest (heavy — run overnight)

```powershell
# Disable enrichment HTTP to save RAM/time during bulk ingest
$env:ENRICH_GEOCODE="false"
$env:ENRICH_HABITAT="false"
$env:ENRICH_WEATHER="false"
$env:ENRICH_OSM="false"

python scripts/run_harvest_profile.py catalog_build
```

Monitor:

```powershell
curl http://localhost:8000/v1/admin/harvest-runs -H "X-API-Key: $env:ADMIN_API_KEY"
```

## 3. Static dataset import — FSD50K (heavy if copying audio)

Download FSD50K from [Zenodo](https://zenodo.org/records/4060432) on the heavy machine, then:

```powershell
# Metadata + audio from local extract (no re-download from Freesound)
starscream-import fsd50k C:\data\FSD50K\FSD50K.metadata\dev.csv `
  --audio-dir C:\data\FSD50K\FSD50K.dev_audio `
  --split dev --limit 1000

# Metadata only (pointer rows; audio stays on disk until you copy)
starscream-import fsd50k C:\data\FSD50K\FSD50K.metadata\dev.csv --split dev --no-audio
```

Re-run `python -m starscream.seed` once so source slug `fsd50k` exists.

### ESC-50 (metadata index)

```powershell
starscream-import esc50 C:\data\ESC-50\meta\esc50.csv --no-audio
```

See [IMPORTERS.md](./IMPORTERS.md).

Batch profiles (edit `CHANGE_ME` paths in `config/import_profiles.json` first):

```powershell
python scripts/run_import_profile.py --list
python scripts/run_import_profile.py esc50_metadata --dry-run
python scripts/run_import_profile.py static_datasets_light
```

## 4. Export catalog (medium–heavy)

```powershell
# Light: JSONL metadata only
starscream-export run .\corpus\ --format jsonl --no-audio

# Heavy: includes audio bytes / parquet
pip install -e ".[export]"
starscream-export run .\corpus\ --format all
```

## 5. Catalog-only cleanup (optional)

Clear local audio pointers on federated rows (keeps contributor uploads):

```powershell
python scripts/catalog_purge_federated_audio.py --dry-run
python scripts/catalog_purge_federated_audio.py
```

Ensure `.env` has `CATALOG_ONLY=true`.

## 6. Check corpus size

```powershell
python scripts/corpus_report.py
curl http://localhost:8000/v1/stats
curl "http://localhost:8000/v1/search?q=bird&limit=5"
```

Training export guide: [TRAINING_EXPORT.md](./TRAINING_EXPORT.md)

## Suggested order

1. Metadata harvest (all sources, `--no-download`)
2. FSD50K metadata import (or small `--limit` with audio on server)
3. Freesound + iNaturalist audio harvest (overnight, enrichment off)
4. JSONL export → spot-check rows before release
5. Scale pages / remove `--limit`
