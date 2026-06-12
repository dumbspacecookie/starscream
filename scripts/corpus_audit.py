#!/usr/bin/env python3
"""Summarize corpus quality from Postgres into JSON (for review before release)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from starscream.config import get_settings
from starscream.db.models import LicenseType, Recording, Source

WEAK_OBJECT_WORDS = frozenset(
    {"the", "a", "an", "npr", "pri", "episode", "wall", "quick", "part", "show"}
)


def _grounded(rec: Recording) -> bool:
    return bool(rec.source_object and rec.source_action)


def _sample_rows(session, source_slug: str, limit: int = 3) -> list[dict]:
    rows = session.execute(
        select(Recording, Source.slug)
        .join(Source, Recording.source_id == Source.id)
        .where(Source.slug == source_slug)
        .order_by(Recording.recorded_at.desc())
        .limit(limit)
    ).all()
    samples = []
    for rec, slug in rows:
        wm = rec.world_model_labels or {}
        samples.append(
            {
                "id": str(rec.id),
                "source": slug,
                "title": rec.title,
                "source_object": rec.source_object,
                "source_action": rec.source_action,
                "license": rec.license.value if rec.license else None,
                "has_audio": bool(rec.flac_key or rec.mp3_key),
                "external_url": rec.external_url,
                "taxonomy_code": rec.taxonomy_code,
                "wm_object_category": wm.get("object_category"),
                "wm_interaction_type": wm.get("interaction_type"),
            }
        )
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write corpus quality summary JSON")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("corpus/catalog_audit.json"),
        help="Write audit JSON here",
    )
    parser.add_argument(
        "--samples-per-source",
        type=int,
        default=3,
        help="Example rows per source slug",
    )
    args = parser.parse_args(argv)

    engine = create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    session = sessionmaker(bind=engine)()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"Cannot connect to Postgres: {exc}", file=sys.stderr)
        return 1

    try:
        total = session.scalar(select(func.count()).select_from(Recording)) or 0
        with_audio = session.scalar(
            select(func.count())
            .select_from(Recording)
            .where(Recording.flac_key.isnot(None) | Recording.mp3_key.isnot(None))
        ) or 0

        by_source = dict(
            session.execute(
                select(Source.slug, func.count(Recording.id))
                .join(Recording, Recording.source_id == Source.id)
                .group_by(Source.slug)
            ).all()
        )

        license_counts = dict(
            session.execute(
                select(Recording.license, func.count(Recording.id)).group_by(Recording.license)
            ).all()
        )
        license_counts = {
            (lic.value if isinstance(lic, LicenseType) else str(lic)): count
            for lic, count in license_counts.items()
        }

        taxonomy_counts = dict(
            session.execute(
                select(Recording.taxonomy_code, func.count(Recording.id))
                .group_by(Recording.taxonomy_code)
                .order_by(func.count(Recording.id).desc())
                .limit(15)
            ).all()
        )

        all_recs = session.scalars(
            select(Recording).where(Recording.source_object.isnot(None))
        ).all()
        grounded = sum(1 for r in all_recs if _grounded(r))
        weak_objects = sum(
            1
            for r in all_recs
            if r.source_object
            and r.source_object.strip().lower() in WEAK_OBJECT_WORDS
        )

        object_counter: Counter[str] = Counter()
        for r in all_recs:
            if r.source_object:
                object_counter[r.source_object.strip().lower()] += 1
        top_objects = object_counter.most_common(15)

        samples = {
            slug: _sample_rows(session, slug, args.samples_per_source)
            for slug in sorted(by_source)
        }

        audit = {
            "total_recordings": total,
            "with_local_audio": with_audio,
            "pointer_only": total - with_audio,
            "by_source": by_source,
            "by_license": license_counts,
            "top_taxonomy_codes": taxonomy_counts,
            "grounding": {
                "grounded_count": grounded,
                "grounded_pct": round(100.0 * grounded / total, 1) if total else 0.0,
                "weak_source_object_count": weak_objects,
                "weak_source_object_pct": round(100.0 * weak_objects / total, 1) if total else 0.0,
            },
            "top_source_objects": [{"object": obj, "count": n} for obj, n in top_objects],
            "samples_by_source": samples,
            "notes": [
                "weak_source_object: vague single-word labels (the, npr, pri, …)",
                "CC-BY-NC and pointer-only rows link out; no local audio",
                "Run validate_export_sample.py on exported JSONL for row checks",
            ],
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(json.dumps(audit, indent=2))
        print(f"\nWrote {args.output}", file=sys.stderr)
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
