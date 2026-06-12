# Contributing Sounds to Starscream

Starscream is an open acoustic corpus built to help **transformers and world models understand the physical world through sound**. Every contribution should tie raw audio to the real object, action, place, and physical properties that produced it.

## Why this matters

Most audio datasets are labeled with abstract categories ("dog bark", "car horn"). World models need more: they must learn that a *specific kind of door* makes a *specific kind of closing sound* in a *specific environment*. Starscream contributions are structured to teach that causal chain.

---

## What to contribute

**Anything that makes a distinct sound in the physical world:**

- Objects interacting (doors, tools, utensils, machinery)
- Living things (birds, insects, mammals, plants in wind)
- Natural phenomena (rain, thunder, rivers, wind through trees)
- Human activity (footsteps, speech in context, marketplace ambience)
- Built environments (traffic, transit, construction, HVAC)

**Priority gaps** (especially valuable):
- Underrepresented biomes and languages
- Rare mechanical or industrial sounds
- Sounds at biome/urban boundaries
- Before-and-after recordings of changing environments

---

## Audio requirements (strict)

| Requirement | Rule |
|---|---|
| **Format** | Lossless only: `.wav`, `.flac`, `.aiff` |
| **Sample rate** | Minimum 44.1 kHz (48 kHz or 96 kHz preferred) |
| **Bit depth** | Minimum 16-bit (24-bit preferred) |
| **Channels** | Mono or stereo as recorded — do not artificially upmix |
| **Processing** | **None.** No MP3, no noise reduction, no EQ, no normalization, no trimming of silence unless the silence is not part of the event |
| **Duration** | 0.5 seconds to 6 hours per clip |
| **Pairing** | Every audio file requires a `manifest.json` sidecar |

Rejected: MP3, M4A, AAC, OGG, Opus, or any lossy derivative.

---

## Metadata requirements

### Required fields

Every contribution **must** include:

| Field | What to write | Example |
|---|---|---|
| `title` | Short descriptive name | `"Oak hallway door closing with latch"` |
| `source_object` | **What** produced the sound (noun) | `"solid oak interior door with brass latch"` |
| `source_action` | **What happened** (verb phrase) | `"closing from half-open, latch clicking into frame"` |
| `recorded_at` | Exact UTC timestamp | `"2026-03-15T14:32:00+00:00"` |
| `location` | GPS coordinates + place name | `{"lat": 40.758, "lng": -73.985, "name": "...", "country_code": "US"}` |
| `license` | `CC0` or `CC-BY` only | `"CC0"` |
| `audio_filename` | Paired raw file name | `"door_close_raw.wav"` |
| `physical_properties` | Structured world-model labels | See below |

### `physical_properties` (required)

These fields ground models in physical causality:

```json
{
  "object_category": "furniture",
  "interaction_type": "impact",
  "estimated_size": "large",
  "force_level": "moderate",
  "repeatability": "one_shot",
  "material_state": "solid"
}
```

| Field | Values (examples) |
|---|---|
| `object_category` | furniture, wildlife, weather, vehicle, tool, body, fluid, structure |
| `interaction_type` | impact, friction, vibration, vocalization, flow, resonance, combustion |
| `estimated_size` | tiny, small, medium, large, massive |
| `force_level` | gentle, moderate, forceful, explosive |
| `repeatability` | one_shot, periodic, continuous, irregular |
| `material_state` | solid, liquid, gas, granular, composite |

### Strongly recommended

| Field | Why |
|---|---|
| `taxonomy_code` | Starscream branch, e.g. `WILDLIFE.BIRD`, `URBAN.TRAFFIC` |
| `description` | Recording context, mic placement, why it matters |
| `tags` | Searchable keywords: `["door", "wood", "latch", "indoor"]` |
| `material` | Primary substance: wood, metal, glass, water, organic |
| `environment` | indoor, outdoor, underwater, vehicle, mixed |
| `distance_m` | Distance from mic to sound source |
| `mic_orientation` | facing_source, ambient, overhead |
| `background_noise_level` | silent, quiet, moderate, noisy |
| `other_sounds_present` | What else is audible in the clip |
| `recorder_type` / `recorder_model` | Provenance for researchers |

---

## How to contribute

### 1. Initialize a contribution package

```bash
starscream-contrib init my-recording/
```

This creates `manifest.json` from the example template.

### 2. Record raw audio

- Use the best mic available (phone is fine for v0)
- Record at the highest sample rate your device supports
- Note GPS coordinates and exact time
- Capture the sound as it naturally occurred

### 3. Fill in manifest.json

Edit every required field. Be specific:

- Bad `source_object`: `"door"`
- Good `source_object`: `"solid oak interior door with brass latch"`

- Bad `source_action`: `"closing"`
- Good `source_action`: `"closing from half-open, latch clicking into frame"`

### 4. Validate locally

```bash
starscream-contrib validate my-recording/manifest.json
```

Fix all errors before uploading. Warnings are advisory but improve corpus quality.

### 5. Upload

```bash
starscream-contrib upload my-recording/manifest.json --api http://localhost:8000
```

Or use the API directly:

```
POST /v1/contrib/upload
  manifest_json: <ContributionManifest JSON>
  audio: <raw file>
```

---

## License

All direct contributions must be **CC0** or **CC-BY**.

- **CC0**: public domain dedication (preferred)
- **CC-BY**: credit required — your `contributor_name` is stored for attribution

We do **not** accept CC-BY-NC or CC-BY-ND for direct uploads. (Federated archives with NC licenses are stored as metadata pointers only.)

---

## Quality guidelines

**Do:**
- Record the actual physical event, not a playback from speakers
- Describe the source object as precisely as you can
- Include ambient context (what else is audible)
- Tag generously for search and ML clustering
- Submit one distinct event per file when possible

**Don't:**
- Upload copyrighted music, movie audio, or game sound effects
- Fabricate GPS coordinates
- Process audio before upload
- Use vague labels ("sound", "noise", "thing")
- Submit duplicates of existing recordings

---

## For ML researchers

Bulk exports include:

- Raw FLAC audio
- Full manifest metadata
- `world_model_labels` JSON for structured grounding
- Geo + temporal coordinates
- Spectral fingerprints for deduplication

If you train a model on Starscream data, publish a model card crediting the corpus and linking to `data.starscream.org`.

---

## Questions

- API docs: `/docs` when the server is running
- Manifest schema: [METADATA_SCHEMA.md](./METADATA_SCHEMA.md)
- Platform spec: [starscream-spec.md](../starscream-spec.md)
