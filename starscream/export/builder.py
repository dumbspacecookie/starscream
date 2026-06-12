import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from starscream.db.models import Recording
from starscream.export.records import fetch_recordings, recording_to_row
from starscream.export.split import assign_split
from starscream.storage import get_audio_bytes

DATASET_CARD = """---
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
  - n<1K
---

# Starscream Acoustic Corpus

Grounded acoustic dataset for training transformers and world models on physical causality.

Every row links raw audio to:
- **source_object** — what produced the sound
- **source_action** — what happened
- **location** — lat/lng + place metadata
- **world_model_labels** — structured physical properties

## Usage

```python
# JSONL
import json
rows = [json.loads(line) for line in open("data/train.jsonl")]

# Parquet
import pandas as pd
df = pd.read_parquet("data/train.parquet")

# Hugging Face Datasets
from datasets import load_from_disk
ds = load_from_disk("hf_dataset")
```

## Citation

If you train a model on this data, publish a model card crediting the Starscream corpus
and individual contributors (see `contributor_name` / `contributor_id` fields).

## License

Per-row licenses are in the `license` column (CC0 or CC-BY). See https://starscream.org for terms.
"""


@dataclass
class ExportResult:
    output_dir: Path
    total: int
    train_count: int
    val_count: int
    formats: list[str]
    audio_downloaded: int


def export_dataset(
    db: Session,
    output_dir: Path,
    *,
    fmt: str = "jsonl",
    split_by: str = "country",
    contributions_only: bool = False,
    download_audio: bool = True,
    limit: int | None = None,
) -> ExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = output_dir / "audio"
    if download_audio:
        audio_dir.mkdir(exist_ok=True)

    rows = fetch_recordings(
        db,
        contributions_only=contributions_only,
        with_audio_only=download_audio,
        limit=limit,
    )

    export_rows: list[dict] = []
    audio_downloaded = 0

    for recording, lat, lng in rows:
        audio_rel: str | None = None
        if download_audio and recording.flac_key:
            data = get_audio_bytes(recording.flac_key)
            if data:
                audio_rel = f"audio/{recording.id}.flac"
                (output_dir / audio_rel).write_bytes(data)
                audio_downloaded += 1

        split_key = _split_key(recording, split_by)
        split = assign_split(split_key)
        export_rows.append(recording_to_row(recording, lat, lng, audio_rel, split))

    train_rows = [r for r in export_rows if r["split"] == "train"]
    val_rows = [r for r in export_rows if r["split"] == "val"]

    formats_written: list[str] = []

    if fmt in ("jsonl", "all"):
        _write_jsonl(output_dir / "train.jsonl", train_rows)
        _write_jsonl(output_dir / "val.jsonl", val_rows)
        _write_jsonl(output_dir / "dataset.jsonl", export_rows)
        formats_written.append("jsonl")

    if fmt in ("parquet", "all"):
        _write_parquet(output_dir / "train.parquet", train_rows)
        _write_parquet(output_dir / "val.parquet", val_rows)
        _write_parquet(output_dir / "dataset.parquet", export_rows)
        formats_written.append("parquet")

    if fmt in ("hf", "all"):
        _write_hf_dataset(output_dir / "hf_dataset", train_rows, val_rows)
        formats_written.append("hf")

    (output_dir / "README.md").write_text(DATASET_CARD, encoding="utf-8")
    (output_dir / "export_meta.json").write_text(
        json.dumps(
            {
                "total": len(export_rows),
                "train": len(train_rows),
                "val": len(val_rows),
                "split_by": split_by,
                "formats": formats_written,
                "audio_downloaded": audio_downloaded,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return ExportResult(
        output_dir=output_dir,
        total=len(export_rows),
        train_count=len(train_rows),
        val_count=len(val_rows),
        formats=formats_written,
        audio_downloaded=audio_downloaded,
    )


def _split_key(recording: Recording, split_by: str) -> str:
    if split_by == "taxonomy":
        return recording.taxonomy_code or ""
    if split_by == "country":
        return recording.country_code or "unknown"
    if split_by == "none":
        return str(recording.id)
    return recording.country_code or recording.taxonomy_code or str(recording.id)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_parquet(path: Path, rows: list[dict]) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Install export extras: pip install -e '.[export]'") from exc

    if not rows:
        pq.write_table(pa.table({}), path)
        return

    # Serialize nested fields for parquet compatibility
    serialized = []
    for row in rows:
        r = dict(row)
        r["tags"] = json.dumps(r.get("tags") or [])
        r["world_model_labels"] = json.dumps(r.get("world_model_labels") or {})
        serialized.append(r)

    pq.write_table(pa.Table.from_pylist(serialized), path)


def _write_hf_dataset(path: Path, train_rows: list[dict], val_rows: list[dict]) -> None:
    try:
        from datasets import Dataset, DatasetDict
    except ImportError as exc:
        raise ImportError("Install export extras: pip install -e '.[export]'") from exc

    ds = DatasetDict(
        {
            "train": Dataset.from_list(train_rows),
            "validation": Dataset.from_list(val_rows),
        }
    )
    ds.save_to_disk(str(path))
