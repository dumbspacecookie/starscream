---
language: en
license: cc0-1.0
task_categories:
  - audio-classification
  - audio-to-audio
tags:
  - audio
  - world-models
  - physical-grounding
  - bioacoustics
  - starscream
size_categories:
  - 1K<n<10K
---

# Starscream acoustic catalog

Grounded sound metadata for training models on physical causality — what made the noise, what happened, and where.

Most rows are **pointer-only**: metadata plus `external_url` to upstream audio. No audio files ship in this repo.

Every row includes:

- **source_object** — what produced the sound
- **source_action** — what happened
- **location** — lat/lng and place metadata when known
- **world_model_labels** — structured physical tags
- **license** — per-row upstream terms

## Usage

```python
import json

rows = [json.loads(line) for line in open("dataset.jsonl")]
```

Offline search without Docker:

```bash
pip install -e .
python -m starscream.catalog stats
python -m starscream.catalog search "chaffinch" --limit 5
```

See [docs/CATALOG.md](../docs/CATALOG.md) and [docs/TRAINING_EXPORT.md](../docs/TRAINING_EXPORT.md).

## Citation

If you train on this data, credit the Starscream catalog and upstream sources (`external_url`, `license`, contributor fields).

## Maintainer

**dumbspacecookie** — https://github.com/dumbspacecookie/starscream

## License

Per-row licenses are in the `license` field. See [docs/DATA_LICENSE.md](../docs/DATA_LICENSE.md).
