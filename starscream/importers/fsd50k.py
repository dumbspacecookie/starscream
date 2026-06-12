"""Import FSD50K metadata CSV into Starscream via federation ingest.

Expects the Zenodo layout:
  FSD50K.metadata/dev.csv | eval.csv
  FSD50K.dev_audio/*.wav   | FSD50K.eval_audio/*.wav

Per-clip license varies (Freesound origin). Default: CC-BY with optional local
audio copy when --audio-dir is set and file exists.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.db.models import Source
from starscream.federation.base import FederatedRecord
from starscream.federation.freesound import map_taxonomy
from starscream.federation.grounding import ground_federated_fields
from starscream.federation.ingest import IngestResult, ingest_federated_records

logger = logging.getLogger(__name__)

FSD50K_SLUG = "fsd50k"
ZENODO_URL = "https://zenodo.org/records/4060432"


def _parse_labels(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _freesound_id_from_fname(fname: str) -> str:
    stem = Path(fname).stem
    match = re.match(r"^(\d+)", stem)
    return match.group(1) if match else stem


def load_fsd50k_csv(
    csv_path: Path,
    *,
    audio_dir: Path | None = None,
    split: str = "dev",
    limit: int | None = None,
    copy_audio: bool = True,
) -> list[FederatedRecord]:
    """Parse FSD50K metadata CSV into FederatedRecord list."""
    records: list[FederatedRecord] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            fname = (row.get("fname") or row.get("filename") or "").strip()
            if not fname:
                continue

            labels = _parse_labels(row.get("labels") or row.get("label") or "")
            title = labels[0] if labels else fname
            taxonomy = map_taxonomy(labels, title)
            source_object, source_action = ground_federated_fields(title=title, tags=labels)
            fs_id = _freesound_id_from_fname(fname)
            external_url = f"https://freesound.org/people/browse/?f={fs_id}"

            record = FederatedRecord(
                external_id=f"fsd50k-{split}-{fname}",
                external_url=external_url,
                taxonomy_code=taxonomy,
                lat=0.0,
                lng=0.0,
                recorded_at=datetime.now(timezone.utc),
                license="CC-BY",
                title=title,
                description=f"FSD50K {split}: {', '.join(labels[:5])}" if labels else None,
                tags=labels,
                source_object=source_object,
                source_action=source_action,
                duration_s=None,
                preview_url=None,
            )

            if copy_audio and audio_dir:
                audio_path = audio_dir / fname
                if not audio_path.suffix:
                    audio_path = audio_path.with_suffix(".wav")
                if audio_path.is_file():
                    record._preview_bytes = audio_path.read_bytes()  # type: ignore[attr-defined]

            records.append(record)
            if limit and len(records) >= limit:
                break

    return records


def import_fsd50k(
    db: Session,
    csv_path: Path,
    *,
    audio_dir: Path | None = None,
    split: str = "dev",
    limit: int | None = None,
    copy_audio: bool = True,
) -> IngestResult:
    """Import FSD50K rows from a local CSV extract.

    Set ENRICH_*=false in .env before bulk import to avoid enrichment HTTP.
    """
    source = db.execute(select(Source).where(Source.slug == FSD50K_SLUG)).scalar_one_or_none()
    if not source:
        raise ValueError(
            f"Source '{FSD50K_SLUG}' not seeded — run: python -m starscream.seed"
        )

    records = load_fsd50k_csv(
        csv_path,
        audio_dir=audio_dir,
        split=split,
        limit=limit,
        copy_audio=copy_audio,
    )
    if not records:
        return IngestResult(created=0, skipped=0, failed=0, errors=["No rows parsed from CSV"])

    return ingest_federated_records(
        db,
        source,
        records,
        download_audio=copy_audio and audio_dir is not None,
    )
