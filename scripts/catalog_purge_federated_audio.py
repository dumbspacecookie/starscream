#!/usr/bin/env python3
"""Clear local audio keys on federated rows (catalog-only posture).

Keeps contributor uploads intact. Does not delete MinIO objects.
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from starscream.config import get_settings
from starscream.db.models import Recording, Source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove local audio pointers from federated (non-contributor) recordings",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only",
    )
    args = parser.parse_args(argv)

    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()
    try:
        contributor_source = session.execute(
            select(Source.id).where(Source.slug == "contributor")
        ).scalar_one()

        q = (
            select(Recording)
            .where(Recording.is_contribution.is_(False))
            .where(Recording.source_id != contributor_source)
            .where(
                Recording.flac_key.isnot(None)
                | Recording.mp3_key.isnot(None)
                | Recording.spectrogram_key.isnot(None)
            )
        )
        rows = list(session.scalars(q).all())
        print(f"Federated rows with local audio pointers: {len(rows)}")

        if args.dry_run or not rows:
            return 0

        ids = [r.id for r in rows]
        session.execute(
            update(Recording)
            .where(Recording.id.in_(ids))
            .values(flac_key=None, mp3_key=None, spectrogram_key=None)
        )
        session.commit()
        print(f"Cleared audio keys on {len(ids)} federated recordings")
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
