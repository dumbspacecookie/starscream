# Exporting the Starscream Dataset

Export the corpus for transformer / world model training.

## Quick start

```bash
# JSONL (no extra deps)
starscream-export run ./dataset/ --format jsonl

# Parquet + Hugging Face (requires export extras)
pip install -e ".[export]"
starscream-export run ./dataset/ --format all --split-by country
```

## Output layout

```
dataset/
├── audio/              # FLAC files (one per recording)
├── train.jsonl
├── val.jsonl
├── dataset.jsonl       # full corpus
├── train.parquet       # if --format parquet or all
├── val.parquet
├── hf_dataset/         # if --format hf or all
├── README.md           # Hugging Face dataset card
└── export_meta.json    # export stats
```

## Row schema

Each row includes:

| Field | Description |
|---|---|
| `audio` | Relative path to FLAC file (null when `--no-audio` or pointer-only) |
| `has_audio` | Whether local FLAC/MP3 exists in Starscream storage |
| `external_id`, `external_url` | Federated source identifiers |
| `source_slug` | Harvest/import source (`freesound`, `esc50`, …) |
| `title`, `source_object`, `source_action` | Causal grounding |
| `lat`, `lng`, `location_name`, `country_code` | Spatial grounding |
| `world_model_labels` | Full structured physical properties |
| `wm_object_category`, `wm_interaction_type`, ... | Flattened WM fields |
| `tags`, `material`, `environment` | Search / cluster labels |
| `split` | `train` or `val` (deterministic by country/taxonomy) |

## Options

| Flag | Default | Description |
|---|---|---|
| `--format` | `jsonl` | `jsonl`, `parquet`, `hf`, or `all` |
| `--split-by` | `country` | Train/val split key: `country`, `taxonomy`, `none` |
| `--contributions-only` | off | Exclude federated archive records |
| `--no-audio` | off | Metadata-only export |
| `--limit` | none | Cap number of recordings |

## Publish to Hugging Face Hub

After exporting, push the dataset directory to a Hugging Face dataset repo:

```bash
pip install -e ".[export]"

# Export first (README.md is required for publish)
starscream-export run ./dataset/ --format all --split-by country

# Publish (token via flag or HF_TOKEN env var)
starscream-export publish ./dataset/ --repo-id your-user/starscream-corpus
starscream-export publish ./dataset/ --repo-id your-user/starscream-corpus --private
export HF_TOKEN=hf_xxx
starscream-export publish ./dataset/ --repo-id your-user/starscream-corpus
```

`publish` uploads all files under the export directory (JSONL/Parquet, `audio/`, `hf_dataset/`, `README.md`) via `huggingface_hub`. The repo is created if it does not exist (`--private` for restricted access).

## Loading in Python

```python
# Hugging Face Datasets
from datasets import load_from_disk
ds = load_from_disk("dataset/hf_dataset")
print(ds["train"][0]["source_object"])

# JSONL
import json
rows = [json.loads(l) for l in open("dataset/train.jsonl")]
```

## Batch upload (contributors)

```bash
# Validate a folder of manifest+audio packages
starscream-contrib validate-batch ./recordings/

# Upload all valid packages
starscream-contrib upload-batch ./recordings/ --api http://localhost:8000

# Or ZIP upload via API
curl -X POST http://localhost:8000/v1/contrib/upload-batch \
  -F "archive=@recordings.zip"
```
