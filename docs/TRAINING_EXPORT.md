# Training export guide

How to turn Starscream JSONL into a dataset for acoustic ML or world-model work.

## Export modes

| Goal | Command |
|------|---------|
| Metadata catalog (default) | `starscream-export run ./corpus/ --format jsonl` |
| Rows with local audio only | `starscream-export run ./corpus/ --format jsonl --with-audio` |
| Contributor uploads only | `starscream-export run ./corpus/ --format jsonl --contributions-only` |
| Hugging Face layout | `pip install -e ".[export]"` then `--format hf` |

Large exports with audio belong on a machine with Docker and disk space — see [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md).

## Fields worth keeping

Each JSONL row is one grounded sound event:

| Field | Meaning |
|-------|---------|
| `source_object` | What made the sound |
| `source_action` | What it was doing |
| `world_model_labels` | Structured tags (`object_category`, `interaction_type`, …) |
| `lat`, `lng`, `location_name` | Where (when known) |
| `license`, `external_url` | Legal terms and upstream link |
| `taxonomy_code` | Starscream category (`WILDLIFE.BIRD`, …) |

Most federated rows are **pointer-only** (`has_audio: false`). Use `external_url` to fetch audio upstream, or filter to rows you are allowed to mirror locally.

## Minimal loader

```python
import json
from pathlib import Path

def load_jsonl(path: Path, *, audio_only: bool = False):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if audio_only and not row.get("has_audio"):
            continue
        rows.append(row)
    return rows

rows = load_jsonl(Path("corpus/dataset.jsonl"))
```

## Sanity checks

```bash
python scripts/corpus_report.py
python scripts/validate_export_sample.py corpus/dataset.jsonl --metadata-only
```

## Suggested filters for training

- Drop rows with missing `source_object` or `wm_object_category == "unknown"`.
- Stratify by `country_code` or `taxonomy_code` if you care about geographic or taxonomic balance.
- For on-disk audio: `license in ("CC0", "CC-BY", "public-domain")` and `has_audio == true`. See [REDISTRIBUTION.md](./REDISTRIBUTION.md).

## See also

- [REDISTRIBUTION.md](./REDISTRIBUTION.md) — what you may ship in git
- [EXPORT.md](./EXPORT.md) — CLI details
- [CATALOG.md](./CATALOG.md) — offline search without Docker
- [METADATA_SCHEMA.md](./METADATA_SCHEMA.md) — full field list
