# Starscream Metadata Schema

Canonical schema: `starscream.contrib.schema.ContributionManifest`

Every user contribution is a **paired package**:

```
my-recording/
├── manifest.json      # This schema
└── door_close_raw.wav # Raw audio (lossless)
```

---

## Design principles

1. **Causal grounding** — every clip links audio → object → action → place → time
2. **Raw fidelity** — lossless audio, no processing, technical metadata preserved
3. **World model labels** — structured `physical_properties` for transformer training
4. **Open licensing** — CC0/CC-BY only for direct contributions
5. **Searchable tags** — freeform lowercase tags normalized to `snake_case`

---

## Full schema reference

### Identity

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string (3–256) | yes | Human-readable clip name |
| `source_object` | string (2–256) | yes | Physical entity that produced the sound |
| `source_action` | string (2–256) | yes | Event/action that caused the sound |
| `description` | string (≤2000) | no | Recording context and narrative |

### Temporal + spatial

| Field | Type | Required | Description |
|---|---|---|---|
| `recorded_at` | ISO 8601 datetime | yes | Exact UTC capture time |
| `location.lat` | float [-90, 90] | yes | WGS84 latitude |
| `location.lng` | float [-180, 180] | yes | WGS84 longitude |
| `location.name` | string | no | Human place name |
| `location.country_code` | ISO 3166-1 alpha-2 | no | Country |
| `location.altitude_m` | float | no | Elevation |

### Licensing + pairing

| Field | Type | Required | Description |
|---|---|---|---|
| `license` | `CC0` \| `CC-BY` | yes | Open license only |
| `audio_filename` | string | yes | Must end in `.wav`, `.flac`, `.aiff` |

### Classification

| Field | Type | Required | Description |
|---|---|---|---|
| `taxonomy_code` | string | default `NATURAL` | Starscream taxonomy branch |
| `tags` | string[] | no | Normalized to lowercase snake_case |

### Physical grounding

| Field | Type | Required | Description |
|---|---|---|---|
| `material` | string | no | wood, metal, glass, water, organic, synthetic |
| `environment` | enum | no | indoor, outdoor, underwater, vehicle, mixed, unknown |
| `distance_m` | float [0–1000] | no | Mic-to-source distance |
| `mic_orientation` | string | no | facing_source, ambient, overhead, binaural_* |
| `background_noise_level` | enum | no | silent, quiet, moderate, noisy |
| `other_sounds_present` | string[] | no | Co-occurring audible events |

### Recorder provenance

| Field | Type | Required | Description |
|---|---|---|---|
| `recorder_type` | enum | no | smartphone, binaural, hydrophone, ultrasonic, iot |
| `recorder_model` | string | no | Device model |
| `sample_rate_hz` | int [8000–384000] | no | Verified against file on upload |
| `channels` | int [1–32] | no | Channel count |
| `bit_depth` | int [8–32] | no | Bit depth |

### Attribution

| Field | Type | Required | Description |
|---|---|---|---|
| `contributor_id` | string | no | Stable ID (ORCID, hashed email) |
| `contributor_name` | string | no | Display name for CC-BY credit |

### World model labels

| Field | Type | Required | Description |
|---|---|---|---|
| `physical_properties` | object | **yes** (strict mode) | Structured grounding labels |

#### `physical_properties` object

| Field | Type | Required |
|---|---|---|
| `object_category` | string | yes |
| `interaction_type` | string | yes |
| `estimated_size` | string | no |
| `force_level` | string | no |
| `repeatability` | string | no |
| `material_state` | string | no |

### Scene graph + timed events (optional)

Structured scene and event annotations for world-model training. Both fields are optional for backward compatibility with Phase 1 manifests.

| Field | Type | Required | Description |
|---|---|---|---|
| `events` | `SoundEvent[]` | no | Top-level timed events in the clip |
| `scene_graph` | `SceneGraph` | no | Entities present and sub-events referencing them |

#### `SoundEvent` object

| Field | Type | Required | Description |
|---|---|---|---|
| `t_start_s` | float ≥ 0 | yes | Event start (seconds from clip start) |
| `t_end_s` | float ≥ 0 | yes | Event end (must be > `t_start_s`) |
| `source_object` | string | yes | What produced this event |
| `source_action` | string | yes | Action that caused the event |
| `entity_id` | string | no | Reference to `SceneEntity.id` in `scene_graph` |

#### `SceneEntity` object

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier referenced by `entity_id` |
| `label` | string | yes | Human-readable name |
| `category` | string | yes | Broad category (furniture, wildlife, hardware, etc.) |
| `material` | string | no | Primary material |

#### `SceneGraph` object

| Field | Type | Required | Description |
|---|---|---|---|
| `entities` | `SceneEntity[]` | no | Objects present in the scene (ids must be unique) |
| `events` | `SoundEvent[]` | no | Timed events; `entity_id` must match an entity |

---

## API storage mapping

On ingest, manifest fields map to the `recordings` table:

| Manifest field | DB column |
|---|---|
| `title` | `title` |
| `source_object` | `source_object` |
| `source_action` | `source_action` |
| `tags` | `tags` (JSON array) |
| `physical_properties` | `world_model_labels` (JSON) |
| `events` | `events` (JSON array) |
| `scene_graph` | `scene_graph` (JSON object) |
| `environment` | `environment` |
| ... | ... |

---

## Validation rules

The `validate_contribution()` function enforces:

- Raw lossless audio present
- Sample rate ≥ 44100 Hz
- Duration 0.5s – 6h
- `physical_properties` present (strict mode)
- License is CC0 or CC-BY
- `audio_filename` extension is lossless
- Event times (`events[]` and `scene_graph.events[]`) fall within audio duration
- `entity_id` on events references an id in `scene_graph.entities`

Warnings (non-blocking) for missing tags, material, environment, description.

---

## Example

See [manifest.example.json](../starscream/contrib/templates/manifest.example.json).

```bash
starscream-contrib init
starscream-contrib validate manifest.json
```
