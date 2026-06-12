# Starscream
## Platform Specification v0.1

*The open, permanent, public-domain catalog of all sound on Earth.*

---

## Vision

Starscream is infrastructure — the same class of project as OpenStreetMap, Internet Archive, or Wikipedia. Not a product. Not a startup. A permanent commons.

The goal: **every distinct acoustic phenomenon on Earth, cataloged, timestamped, geolocated, and freely available to anyone, forever.**

A core purpose: **ground transformers and world models in physical reality through sound.** Every recording links raw audio to what produced it, what action caused it, where it happened, and structured physical properties — so models can learn causality, not just classification labels.

---

## What makes this different from what exists

| Project | What it is | What it lacks |
|---|---|---|
| Freesound | User-uploaded sound effects | No sensor network, no real coverage, upload bias |
| Xeno-canto | Bird recordings, crowdsourced | Wildlife only, no urban/atmospheric/cultural |
| Internet Archive | Audio preservation | Not organized as a searchable acoustic catalog |
| GBIF | Biodiversity occurrence data | Text metadata only, no audio |
| OpenStreetMap | Geographic data commons | No acoustic layer |

Starscream is the **acoustic layer** that sits beneath all of the above. It ingests and federates them all, fills the gaps with its own sensor network and crowdsourcing, and exposes everything through a single open API and bulk dataset.

---

## Collection strategy

### 1. Distributed sensor network (IoT)

**Hardware** (open-source reference design):
- Raspberry Pi Zero 2W + USB omnidirectional mic
- 44.1 kHz / 16-bit minimum; 96 kHz preferred for ultrasonic capture
- GPS module (u-blox NEO-6M) for precise coordinates
- 4G/LTE modem or WiFi fallback
- Solar panel + 18650 LiPo for off-grid deployment
- Weatherproof enclosure (IP67), pole-mountable
- Bill of materials: ~$45 per node at scale

**Software**:
- Continuous rolling capture with silence-gated segmentation
- Local preprocessing: normalization, spectral fingerprint computation
- MQTT publish to regional broker on sound event detection
- Firmware OTA update via MQTT retained message

**Deployment targets** (priority order):
1. Biome boundaries (Amazon/cerrado edge, coral reef margins, tundra treeline)
2. Urban density gradients (city center → suburb → rural)
3. Migration corridors (bird flyways, whale acoustic highways)
4. Culturally significant soundscapes (markets, pilgrimage sites, festivals)
5. Climatically threatened environments (glaciers, reefs, boreal forest)

**Node governance**: anyone can deploy a registered node. Nodes earn a cryptographic identity. Tampered or unreliable nodes are flagged by the network through anomaly detection.

---

### 2. Crowdsourced uploads (open contribution framework)

Starscream ships an open-source contribution framework (`starscream.contrib`) requiring **raw lossless audio + structured manifest** for every upload.

**Contribution package**:
```
my-recording/
├── manifest.json      # ContributionManifest schema
└── event_raw.wav      # Unprocessed WAV/FLAC (≥44.1 kHz, ≥16-bit)
```

**Required metadata** (world-model grounding):
- `title` — descriptive name
- `source_object` — what produced the sound (noun): "oak interior door", "American robin"
- `source_action` — what happened (verb phrase): "closing with latch click", "singing at dawn"
- `recorded_at` + `location` (lat/lng, place name, country)
- `license` — CC0 or CC-BY only
- `physical_properties` — structured labels: object_category, interaction_type, force_level, etc.

**CLI** (`starscream-contrib`):
```bash
starscream-contrib init my-recording/
starscream-contrib validate my-recording/manifest.json
starscream-contrib upload my-recording/manifest.json
```

**API**:
- `POST /v1/contrib/upload` — manifest JSON + raw audio
- `POST /v1/contrib/validate` — dry-run validation
- `GET /v1/contrib/guidelines` — machine-readable rules
- `GET /v1/contrib/tags` — tag registry

**Guidelines**: see `docs/CONTRIBUTING.md` and `docs/METADATA_SCHEMA.md`

**Mobile app** (planned, iOS + Android):
- Tap to record with GPS auto-tag, auto-generates manifest
- Offline-capable: record locally, sync when connected
- Guided taxonomy + physical_properties tagging

**Quality incentives**:
- Contributor leaderboards by country, biome, taxonomy branch
- "First recorder" badge for new acoustic species or locations
- Academic citation credits for contributors whose recordings appear in papers

---

### 3. Federation (harvest existing archives)

**Priority sources and status**:

| Source | Records | Strategy | License |
|---|---|---|---|
| Freesound | 600k+ | API harvest | CC-BY |
| Xeno-canto | 1M+ | API harvest | CC-BY-NC |
| iNaturalist | ~200k audio obs | API harvest | CC-BY |
| Macaulay Library (Cornell) | 1.5M | MOU negotiation | Mixed |
| Internet Archive audio | Millions | OAI-PMH harvest | Mixed |
| NOAA ocean acoustics | Terabytes | Direct partnership | Public domain |
| NASA space sounds | ~500 | Direct | Public domain |

**Federation protocol**:
1. Harvest metadata via source API
2. Store source URL + external ID (never claim ownership of source record)
3. Download audio only for public-domain / CC0 / CC-BY recordings
4. For CC-BY-NC: store metadata + pointer only, no local copy
5. Spectral fingerprint all local copies for cross-source dedup

---

## Data model

Every record has these mandatory fields:

```
id              UUID (permanent, never reused)
spectral_hash   SHA-256 of MFCC fingerprint (deduplication key)
taxonomy_code   Hierarchical dot-notation (WILDLIFE.BIRD.SONGBIRD.THRUSH)
location        GEOGRAPHY(POINT) — WGS84
recorded_at     TIMESTAMPTZ — exact UTC timestamp
source_id       → sources table
license         CC0 | CC-BY | CC-BY-NC | etc.
```

And these contextual fields (best-effort):

```
location_name   Human-readable place (reverse geocoded)
country_code    ISO 3166-1 alpha-2
altitude_m      Elevation above sea level
season          spring | summer | autumn | winter (hemisphere-aware)
habitat         Standardized habitat code (IUCN habitat classification)
weather         Conditions at time of recording
temperature_c   Ambient temperature
recorder_type   binaural | hydrophone | ultrasonic | smartphone | iot
quality         1–5 star (community-rated)
```

**The taxonomy tree** (top level, extensible):
```
WILDLIFE          Birds · mammals · insects · fish · reptiles · amphibians
NATURAL           Rivers · oceans · forests · geological · wind · silence
URBAN             Traffic · crowds · construction · transit · nightlife
CULTURAL          Music · speech · ritual · marketplace · sport · ceremony
MECHANICAL        Industrial · engines · tools · infrastructure
ATMOSPHERIC       Thunder · rain · wind · lightning · aurora
AQUATIC           Underwater ambience · marine mammals · fish sounds
EXTRATERRESTRIAL  Space probes · planetary atmospheres · radio emissions
```

---

## Scale projections

| Year | Records | Storage (FLAC) | Sensors | Contributors |
|---|---|---|---|---|
| Year 1 | 5M | ~50 TB | 500 | 10,000 |
| Year 3 | 50M | ~500 TB | 10,000 | 100,000 |
| Year 5 | 500M | ~5 PB | 100,000 | 1M+ |

Comparison: Internet Archive currently holds ~99 PB total. Wikipedia has ~21M files. This is large but achievable on a 5-year horizon.

**Storage strategy**:
- FLAC originals in geo-distributed object storage (Backblaze B2 + Wasabi + Cloudflare R2)
- MP3 192kbps proxy for streaming API
- Monthly BitTorrent snapshots for full archive distribution (like Wikipedia dumps)
- Seeded by default: every node that downloads runs a seed

---

## Processing pipeline

```
Intake → Validate → Fingerprint → Classify → Enrich → Store → Index
```

**Validate**: format check, duration check (reject <0.5s, flag >6h), GPS sanity check, license verification.

**Fingerprint**: compute MFCC (20 coefficients, mean over 30s window), SHA-256 hash. Compare against existing fingerprints. If match found: link records, prefer higher quality copy.

**Classify**: run BirdNET (birds), YAMNet (general 521-class), custom models for bats (ultrasonic), marine mammals, urban soundscapes. Store confidence scores, not just top class — a recording can have multiple taxonomy codes.

**Enrich**: reverse geocode coordinates → location name + country. Derive season from timestamp + hemisphere. Look up habitat from biome layer (WWF Terrestrial Ecoregions). Match weather from nearest station (Open-Meteo historical API).

**Store**: write FLAC to object store, write metadata to PostgreSQL + PostGIS, update search index (Meilisearch for text, PostGIS for geo queries).

---

## Public API

Fully open. No API key for read. Rate-limited at 1000 req/min per IP.

```
GET /v1/recordings
  ?near=lat,lng&radius_km=50
  ?taxonomy=WILDLIFE.BIRD
  ?recorded_after=2020-01-01
  ?season=spring
  ?habitat=tropical_rainforest
  ?quality_min=4
  ?limit=100&cursor=...

GET /v1/recordings/:id
GET /v1/recordings/:id/audio.flac
GET /v1/recordings/:id/audio.mp3
GET /v1/recordings/:id/spectrogram.png

GET /v1/taxonomy          — full tree
GET /v1/taxonomy/:code    — subtree + recording count
GET /v1/sources           — all federated sources
GET /v1/stats             — global coverage stats
```

**GraphQL endpoint** for complex queries (e.g. "all recordings from within 20km of any coral reef, at dawn, in the last 5 years, minimum quality 4").

**WebSocket stream**: subscribe to real-time ingestion feed filtered by taxonomy or location. Useful for monitoring coverage or research alerts.

---

## Governance

**License**: all contributed recordings must be CC0 or CC-BY. No NC, no ND. Non-CC recordings federated by pointer only.

**Foundation**: Starscream Foundation (nonprofit). Board elected annually by contributors weighted by verified contribution volume. No single organization controls the dataset.

**Dispute resolution**: Wikipedia-style: flag, discuss on talk page, escalate to arbitration committee. Vandalism (fake GPS, fabricated recordings) detected automatically and handled by moderator council.

**Mirroring requirement**: any organization mirroring >10TB of Starscream data must provide a public seed. Infrastructure reciprocity.

**AI training clause**: any model trained on Starscream data must publish a model card crediting the Starscream corpus. Attribution flows to individual contributors through contributor IDs in training metadata.

---

## World model training

Starscream is designed as training infrastructure for multimodal and world models:

| Capability | How Starscream provides it |
|---|---|
| **Physical grounding** | `source_object` + `source_action` tie audio to causality |
| **Spatial grounding** | GPS + environment + distance_m + mic_orientation |
| **Material grounding** | `material` + `physical_properties.material_state` |
| **Temporal grounding** | `recorded_at` + season + repeatability pattern |
| **Multi-sensory bridge** | Structured labels pair with geo/time for fusion with vision maps |
| **Raw fidelity** | Lossless audio preserves spectral detail for representation learning |

Bulk exports include raw FLAC, full manifests, `world_model_labels` JSON, and spectral fingerprints. Models trained on Starscream must publish a model card crediting the corpus.

---

## What this enables

Once you have this infrastructure, a lot becomes possible:

**Science**: global bioacoustic monitoring without dispatching field researchers. Real-time early warning of ecosystem collapse (silence is data). Decade-scale climate impact on soundscapes.

**AI**: the largest open acoustic training corpus ever assembled — with causal grounding for world models, not just class labels. Every sound modality — wildlife, music, speech, industrial, atmospheric — in one structured dataset.

**Culture**: an acoustic time machine. What did the Amazon sound like in 2018 before the fires? What does a Javanese market sound like at 5am? What frequency does a blue whale use in the Atlantic vs Pacific?

**Policy**: acoustic pollution mapping at city-block resolution. Evidence for noise ordinance enforcement. Impact assessment for infrastructure projects.

---

## How to get involved

The project needs, in rough priority order:

1. **Sensor node deployments** — buy a kit, deploy somewhere interesting, leave it running
2. **Federation connectors** — write a harvest connector for a new source archive
3. **ML model contributions** — fine-tune classification models for underrepresented taxa
4. **Infrastructure mirrors** — run a regional object store mirror or Postgres replica
5. **Foundation membership** — governance participation, policy drafting
6. **Field recording** — go outside with a good mic

The code is at `github.com/starscream` (proposed). The data is at `data.starscream.org` (proposed). The community is at `discuss.starscream.org`.

---

*Starscream is infrastructure, not a product. It should exist whether or not anyone profits from it. Like roads, like the electromagnetic spectrum, like the ocean — the sounds of the world belong to everyone.*
