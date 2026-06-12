# Federation — Harvesting External Archives

Starscream federates open sound archives, stores metadata, and downloads audio when licensing permits.

## Seed catalogs

Before harvesting, register federation sources in the database:

```bash
python -m starscream.seed
```

This seeds taxonomy nodes and source catalog entries for all connectors, including **NOAA** (`noaa`) and **NASA** (`nasa`) alongside Freesound, Xeno-canto, iNaturalist, and Internet Archive. Harvest jobs fail fast if a source slug is missing from the catalog.

## Freesound (implemented)

Requires a free API key: https://freesound.org/apiv2/apply

```bash
# .env
FREESOUND_API_KEY=your_key_here

# CLI harvest
starscream-harvest freesound --pages 2 --page-size 50

# Metadata only (no preview download)
starscream-harvest freesound --pages 1 --no-download

# API trigger
curl -X POST "http://localhost:8000/v1/federation/harvest/freesound?pages=1&page_size=25"
```

### What gets harvested

- CC0 and CC-BY sounds only (CC-BY-NC stored as pointer in future connectors)
- Metadata: title, description, tags, taxonomy mapping, external URL
- Preview MP3 (HQ) when download enabled — full-quality requires OAuth2 (planned)
- Deduplication by `source_id` + `external_id`

### Taxonomy mapping

Freesound tags are heuristically mapped to Starscream branches (e.g. `bird` → `WILDLIFE.BIRD`).

## Xeno-canto (implemented)

No API key required. Harvests bird recordings from the Xeno-canto API v2.

```bash
# CLI harvest (default query: all recordings)
starscream-harvest xeno-canto --pages 2 --page-size 50

# Metadata only (CC-BY-NC is always pointer-only — no local audio stored)
starscream-harvest xeno-canto --pages 1 --no-download

# API trigger
curl -X POST "http://localhost:8000/v1/federation/harvest/xeno-canto?pages=1&page_size=50"
```

### What gets harvested

- CC-BY-NC recordings (Xeno-canto default) — **metadata + external URL only**, no local audio copy
- CC-BY recordings (rare) — MP3 download when `--no-download` is not set
- Species → `source_object`, sound type (song/call) → `source_action`
- GPS from recording lat/lng; taxonomy fixed to `WILDLIFE.BIRD`
- Deduplication by `source_id` + `external_id`

API endpoint: `https://xeno-canto.org/api/3/recordings?query={tags}&page={page}&per_page={n}&key={api_key}`

Requires `XENO_CANTO_API_KEY` in `.env` (retrieve at https://xeno-canto.org/account — do not commit keys).

API v3 requires **tagged queries** (not bare species names). Examples:

| Query | Content |
|-------|---------|
| `grp:birds` | All bird recordings |
| `grp:bats` | Bat echolocation / calls |
| `grp:frogs` | Frog vocalizations |
| `grp:grasshoppers` | Insect stridulation |
| `grp:soundscapes` | Ambient nature soundscapes |
| `cnt:Netherlands` | Country filter (combine with `+`) |

Harvest profiles: `raw_world_xc_all`, `raw_world_full` in `config/harvest_profiles.json`.  
Upstream catalog reference: `config/external_sound_repos.json`.

## iNaturalist (implemented)

No API key required. Harvests research-grade observations with sounds via API v1.

```bash
# CLI harvest
starscream-harvest inaturalist --pages 2 --page-size 50

# Metadata + audio download for CC-BY/CC0 sounds only
starscream-harvest inaturalist --pages 1 --no-download
```

### What gets harvested

- Research-grade observations with `has_sounds=true`
- CC-BY and CC0 sound licenses only (NC/SA skipped)
- Species → `source_object`, vocalization → `source_action`
- GPS from observation geojson or location string
- Taxonomy mapped from iconic taxon (Aves → `WILDLIFE.BIRD`, etc.)
- Deduplication by `source_id` + `external_id`

API endpoint: `https://api.inaturalist.org/v1/observations?quality_grade=research&has_sounds=true`

## Internet Archive (implemented)

No API key required. Harvests open audio from archive.org advanced search (opensource audio collection and general audio mediatype).

```bash
# CLI harvest
starscream-harvest internet-archive --pages 2 --page-size 50

# Metadata only (mixed-license items are always pointer-only)
starscream-harvest internet-archive --pages 1 --no-download

# API trigger
curl -X POST "http://localhost:8000/v1/federation/harvest/internet-archive?pages=1&page_size=50"
```

### What gets harvested

- All matching items — mixed or unknown license → **pointer-only** metadata + `https://archive.org/details/{identifier}`
- CC-BY and CC0 items — audio download via metadata API when download enabled
- CC-BY-NC — metadata pointer only (no local audio)
- Title/description keywords mapped to taxonomy (e.g. `bird` → `WILDLIFE.BIRD`, `rain` → `ATMOSPHERIC.RAIN`)
- Deduplication by `source_id` + `external_id`

API endpoint: `https://archive.org/advancedsearch.php?q=collection:opensource_audio OR mediatype:audio`

## NOAA (implemented)

No API key required. Harvests public-domain ocean acoustic samples from NOAA PMEL Acoustics Program and NCEI passive acoustic archive pointers.

```bash
# CLI harvest (curated PMEL WAV catalog + NCEI archive pointer)
starscream-harvest noaa --pages 1 --page-size 20

# Metadata only (skip WAV download)
starscream-harvest noaa --pages 1 --no-download

# API trigger
curl -X POST "http://localhost:8000/v1/federation/harvest/noaa?pages=1&page_size=20"
```

### What gets harvested

- Curated catalog of PMEL whale, seismic, and anthropogenic underwater recordings (WAV)
- NCEI Passive Acoustic Data Collection metadata pointer (no direct audio URL)
- License: **PUBLIC_DOMAIN** — audio download when enabled
- Taxonomy fixed to `AQUATIC`; species/source → `source_object`, call type → `source_action`
- GPS approximated from recording region (PMEL mooring locations)
- Deduplication by `source_id` + `external_id`

Sources: `https://www.pmel.noaa.gov/acoustics/`, `https://www.ncei.noaa.gov/products/passive-acoustic-data`

## NASA (implemented)

No API key required. Harvests public-domain space and mission audio from NASA.gov (Sounds from Beyond, Historical Sounds).

```bash
# CLI harvest (~35 curated WAV/MP3 files)
starscream-harvest nasa --pages 1 --page-size 50

# Metadata only
starscream-harvest nasa --pages 1 --no-download

# API trigger
curl -X POST "http://localhost:8000/v1/federation/harvest/nasa?pages=1&page_size=50"
```

### What gets harvested

- Mars rover/microphone audio, InSight seismometer wind and quakes, Cassini/Saturn plasma waves
- Historic mission comms (Apollo, Mercury, Shuttle) and launch audio
- License: **PUBLIC_DOMAIN** — audio download when enabled
- Taxonomy fixed to `EXTRATERRESTRIAL`; celestial body/mission → `source_object`
- Deduplication by `source_id` + `external_id`

Sources: `https://www.nasa.gov/sounds-from-beyond/`, `https://www.nasa.gov/historical-sounds/`

## Batch harvest scheduler

Run multiple connectors sequentially via `starscream.jobs.harvest_all`. Default sources match `CONNECTORS` in `federation/harvest.py` (freesound, xeno-canto, inaturalist, internet-archive, noaa, nasa):

```bash
# All connectors, one page each
python -m starscream.jobs.harvest_all --pages 1

# Explicit source list
python -m starscream.jobs.harvest_all --sources freesound,xeno-canto,inaturalist --pages 1

# Metadata only (no preview/audio download)
python -m starscream.jobs.harvest_all --sources inaturalist --pages 2 --no-download

# Tune page size
python -m starscream.jobs.harvest_all --pages 2 --page-size 25
```

Logs per-source created/skipped/failed counts. Unknown slugs are skipped with an error. Requires seeded sources (`python -m starscream.seed`) — including NOAA and NASA catalog entries.

Per-source CLI remains available: `starscream-harvest freesound --pages 1`.

## Scheduled harvest (cron / daemon)

Use `starscream.jobs.scheduler` for recurring harvests. Each source run is logged to the `harvest_runs` table (created/skipped/failed counts, status, and page-level errors in `detail.errors`). Inspect recent runs via `GET /v1/admin/harvest-runs` (requires `ADMIN_API_KEY`).

```bash
# One-shot cycle (same as harvest_all, with DB logging)
python -m starscream.jobs.scheduler run-once --pages 1

# Daemon: harvest immediately, then every 24 hours
python -m starscream.jobs.scheduler daemon --interval-hours 24 --pages 1

# Subset of sources, metadata only
python -m starscream.jobs.scheduler run-once --sources xeno-canto,inaturalist --no-download
```

### Windows Task Scheduler

Run a daily harvest without keeping a daemon process:

1. Open **Task Scheduler** → **Create Basic Task**
2. Trigger: **Daily** at 02:00 (or your preferred off-peak time)
3. Action: **Start a program**
   - **Program/script:** `C:\Path\To\python.exe`
   - **Add arguments:** `-m starscream.jobs.scheduler run-once --pages 1`
   - **Start in:** `/path/to/starscream`
4. Ensure `.env` (or system env) sets `DATABASE_URL`, `FREESOUND_API_KEY`, and other required vars for the task's user account.

On Linux/macOS, equivalent cron entry:

```cron
0 2 * * * cd /path/to/starscream && python -m starscream.jobs.scheduler run-once --pages 1
```

## Planned connectors

| Source | License | Status |
|---|---|---|
| Freesound | CC-BY | **Implemented** |
| Xeno-canto | CC-BY-NC | **Implemented** (metadata pointer) |
| iNaturalist | CC-BY | **Implemented** |
| Internet Archive | Mixed | **Implemented** (pointer default) |
| NOAA PMEL / NCEI | Public domain | **Implemented** |
| NASA | Public domain | **Implemented** |

## Web upload UI

Contributors can upload via browser:

```
http://localhost:8000/upload
```

Guided form with validation and GPS fill — submits to `POST /v1/contrib/upload`.
