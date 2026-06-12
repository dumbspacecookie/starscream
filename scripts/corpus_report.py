#!/usr/bin/env python3
"""Read-only corpus stats from Postgres (lightweight, no harvest)."""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from starscream.config import get_settings
from starscream.db.models import Recording, Source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print Starscream corpus statistics")
    parser.add_argument("--top", type=int, default=10, help="Top N source_object values")
    args = parser.parse_args(argv)

    engine = create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    session = sessionmaker(bind=engine)()
    try:
        try:
            session.execute(text("SELECT 1"))
        except Exception as exc:
            print(
                "Cannot connect to Postgres — start the stack first "
                "(docker compose up -d) and check DATABASE_URL in .env",
                file=__import__("sys").stderr,
            )
            print(f"  ({exc})", file=__import__("sys").stderr)
            return 1

        total = session.scalar(select(func.count()).select_from(Recording)) or 0
        with_audio = session.scalar(
            select(func.count()).select_from(Recording).where(Recording.flac_key.isnot(None))
        ) or 0
        pointers = total - with_audio
        contributions = session.scalar(
            select(func.count())
            .select_from(Recording)
            .where(Recording.is_contribution.is_(True))
        ) or 0

        print(f"Total recordings: {total}")
        print(f"  with local audio: {with_audio}")
        print(f"  pointer-only: {pointers}")
        print(f"  contributions: {contributions}")
        print()

        by_source = session.execute(
            select(Source.slug, func.count(Recording.id))
            .join(Recording, Recording.source_id == Source.id)
            .group_by(Source.slug)
            .order_by(func.count(Recording.id).desc())
        ).all()
        print("By source:")
        for slug, count in by_source:
            print(f"  {slug}: {count}")
        print()

        top_objects = session.execute(
            select(Recording.source_object, func.count())
            .where(Recording.source_object.isnot(None))
            .group_by(Recording.source_object)
            .order_by(func.count().desc())
            .limit(args.top)
        ).all()
        print(f"Top {args.top} source_object:")
        for obj, count in top_objects:
            print(f"  {obj}: {count}")
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
