# Redistribution policy — catalog only, no hosting

Starscream is an **acoustic catalog**, not an audio host. The default posture:

1. **Index** sounds (metadata, grounding, license, upstream URL).
2. **Do not** store or redistribute audio bytes unless the row license clearly allows it and you explicitly opt in.
3. Let **upstream archives** keep the files; users fetch from `external_url` when they need audio.

This matches Creative Commons practice: a pointer catalog with correct attribution is generally fine. Re-hosting NC or unknown-license audio is not.

> **Not legal advice.** Confirm with counsel before a large public release.

---

## What Starscream stores

| Tier | `has_audio` | Typical licenses | In Postgres / export |
|------|-------------|------------------|----------------------|
| **Pointer** | `false` | CC-BY-NC, POINTER_ONLY, unclear | Metadata + `external_url` only |
| **Mirror** (opt-in harvest) | `true` | CC0, CC-BY, public-domain | Local object storage (MinIO/S3) — **optional** |

Federation ingest **defaults to pointer-only** for CC-BY-NC and mixed-license sources (xeno-canto, most Internet Archive, NC iNaturalist). See [GOVERNANCE.md](./GOVERNANCE.md).

---

## What belongs in a GitHub repo

GitHub is for **code + small metadata artifacts**, not a sound archive.

| Artifact | OK on GitHub? | Notes |
|----------|---------------|-------|
| Application code, docs, tests | Yes | Primary use |
| Metadata JSONL (`--no-audio` export) | Yes | ~4k rows ≈ few MB; scales to tens of thousands |
| `catalog_audit.json`, harvest profiles | Yes | Review / reproducibility |
| Sample rows (10–100) for CI | Yes | Fixture-sized |
| **Audio files** (FLAC/MP3/WAV) | **No** | 100 MB/file hard limit; repos >1 GB discouraged; LFS is not free at corpus scale |
| Full corpus with audio | **No** | Use upstream URLs, Zenodo, Hugging Face Datasets, or torrents |

**Practical GitHub bundle:** `corpus/dataset.jsonl` (metadata-only), `corpus/catalog_audit.json`, `config/external_sound_repos.json` — all license-tagged, no bytes.

Add `corpus/*.jsonl` to release assets only if you want; keep large exports out of every commit. A `.gitignore` entry for local heavy exports is fine.

---

## License → what you may publish

### In a metadata catalog (JSONL in git)

| Upstream license | Publish metadata + link? | Publish audio in repo? |
|------------------|--------------------------|----------------------|
| CC0 | Yes | Optional (still avoid git for size) |
| CC-BY | Yes, with attribution fields | Optional with attribution |
| CC-BY-NC | Yes (pointer only) | **No** — link out |
| Public domain (NOAA/NASA) | Yes | Optional; prefer link for size |
| Unknown / mixed | Yes (pointer only) | **No** |

Downstream users **do not** need accounts at xeno-canto, iNaturalist, etc. to read your **metadata**. If they want **audio**, they follow `external_url` and comply with that row’s license.

### Required fields per row (already in export)

- `license` — per-recording upstream license
- `external_url` — canonical upstream page or file
- `source_object`, `source_action` — Starscream grounding
- Contributor / recordist attribution where available (`username`, description)

---

## Recommended export for “no hosting”

```powershell
# Metadata catalog only — safe for git
python -m starscream.export.cli run corpus --format jsonl --no-audio
python scripts/validate_export_sample.py corpus/dataset.jsonl --metadata-only
```

Consumers load JSONL and resolve audio at fetch time:

```python
import json

def open_audio(row):
    if row.get("has_audio"):
        # Only if you run a mirror — not the default git posture
        return open(row["audio"], "rb")
    # Default: user fetches from upstream
    return row["external_url"]
```

Filter for rows that are safe to mirror **if** you ever host elsewhere (not GitHub):

```python
REDISTRIBUTABLE = {"CC0", "CC-BY", "public-domain"}
safe = [r for r in rows if r.get("license") in REDISTRIBUTABLE]
```

---

## Upstream sources (reference)

Canonical list: [config/external_sound_repos.json](../config/external_sound_repos.json).  
Harvest behavior: [FEDERATION.md](./FEDERATION.md).

---

## Configuration

Set in `.env`:

```env
CATALOG_ONLY=true
```

When enabled (default):

- Federation harvest does **not** download preview audio unless you pass `--download`
- Export does **not** copy audio unless you pass `--with-audio`
- CC-BY-NC rows remain pointer-only regardless

## Summary

- **Your goal (catalog, no hosting):** supported and license-conservative.
- **GitHub:** great for metadata indexes and code; **not** for audio volume.
- **NC / unclear audio:** metadata in Starscream, files stay at source.
- **CC0 / CC-BY:** metadata always; audio stays upstream unless you deliberately run a separate mirror (S3/HF/Zenodo), not the main git repo.
