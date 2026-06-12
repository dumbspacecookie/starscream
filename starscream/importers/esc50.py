"""Import ESC-50 metadata CSV into Starscream.

Dataset: https://github.com/karolpiczak/ESC-50
License: CC-BY-NC (metadata indexed; audio stored pointer-only per Starscream policy).

Expected layout:
  meta/esc50.csv
  audio/*.wav
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.db.models import Source
from starscream.federation.base import FederatedRecord
from starscream.federation.freesound import map_taxonomy
from starscream.federation.grounding import ground_federated_fields
from starscream.federation.ingest import IngestResult, ingest_federated_records

ESC50_SLUG = "esc50"
ESC50_URL = "https://github.com/karolpiczak/ESC-50"


def load_esc50_csv(
    csv_path: Path,
    *,
    audio_dir: Path | None = None,
    limit: int | None = None,
    copy_audio: bool = True,
) -> list[FederatedRecord]:
    records: list[FederatedRecord] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            fname = (row.get("filename") or row.get("fname") or "").strip()
            category = (row.get("category") or row.get("target") or "").strip()
            if not fname:
                continue

            tags = [category] if category else []
            title = category.replace("_", " ") if category else fname
            taxonomy = map_taxonomy(tags, title)
            source_object, source_action = ground_federated_fields(
                title=title, tags=tags, category=category
            )

            record = FederatedRecord(
                external_id=f"esc50-{fname}",
                external_url=f"{ESC50_URL}/tree/master/audio/{fname}",
                taxonomy_code=taxonomy,
                lat=0.0,
                lng=0.0,
                recorded_at=datetime.now(timezone.utc),
                license="CC-BY-NC",
                title=title,
                description=f"ESC-50 category: {category}" if category else None,
                tags=tags,
                source_object=source_object,
                source_action=source_action,
                duration_s=5.0,
                preview_url=None,
            )

            if copy_audio and audio_dir:
                audio_path = audio_dir / fname
                if audio_path.is_file():
                    record._preview_bytes = audio_path.read_bytes()  # type: ignore[attr-defined]

            records.append(record)
            if limit and len(records) >= limit:
                break

    return records


def import_esc50(
    db: Session,
    csv_path: Path,
    *,
    audio_dir: Path | None = None,
    limit: int | None = None,
    copy_audio: bool = True,
) -> IngestResult:
    source = db.execute(select(Source).where(Source.slug == ESC50_SLUG)).scalar_one_or_none()
    if not source:
        raise ValueError(f"Source '{ESC50_SLUG}' not seeded — run: python -m starscream.seed")

    records = load_esc50_csv(
        csv_path,
        audio_dir=audio_dir,
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
