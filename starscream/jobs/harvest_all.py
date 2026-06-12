"""Run multiple federation harvesters sequentially.

Usage:
    python -m starscream.jobs.harvest_all --sources freesound,xeno-canto,inaturalist --pages 1
"""

from __future__ import annotations

import argparse
import sys

from starscream.config import get_settings
from starscream.db.session import get_session_factory
from starscream.federation.harvest import CONNECTORS, harvest_source_sync
from starscream.jobs.harvest_state import record_failed, record_skipped, record_success, utcnow

DEFAULT_SOURCES = list(CONNECTORS.keys())


def harvest_all(
    sources: list[str],
    *,
    pages: int = 1,
    page_size: int = 50,
    download_previews: bool | None = None,
    query: str | None = None,
) -> int:
    if download_previews is None:
        download_previews = not get_settings().catalog_only
    session = get_session_factory()()
    exit_code = 0
    try:
        for slug in sources:
            print(f"\n=== Harvesting {slug} ({pages} page(s)) ===")
            if query:
                print(f"  query: {query}")
            started_at = utcnow()
            try:
                result = harvest_source_sync(
                    session,
                    slug,
                    pages=pages,
                    page_size=page_size,
                    download_previews=download_previews,
                    query=query,
                )
            except ValueError as exc:
                session.rollback()
                print(f"  SKIP: {exc}", file=sys.stderr)
                record_skipped(session, slug, started_at, message=str(exc))
                exit_code = 1
                continue
            except Exception as exc:
                session.rollback()
                print(f"  FAILED: {exc}", file=sys.stderr)
                record_failed(session, slug, started_at, message=str(exc))
                exit_code = 1
                continue

            record_success(session, slug, started_at, result)
            print(
                f"  {slug}: {result.created} created, "
                f"{result.skipped} skipped, {result.failed} failed"
            )
            for err in result.errors[:5]:
                print(f"    ERROR: {err}", file=sys.stderr)
            if result.failed:
                exit_code = 1
    finally:
        session.close()

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harvest multiple federated sound archives into Starscream",
    )
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"Comma-separated source slugs (default: {','.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument("--pages", type=int, default=1, help="Pages per source")
    parser.add_argument("--page-size", type=int, default=50, help="Records per page")
    parser.add_argument(
        "--query",
        default=None,
        help="Search query for xeno-canto or internet-archive (API v3 tags for XC)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download preview audio when license permits (default off in catalog-only mode)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Metadata only (alias; default when CATALOG_ONLY=true)",
    )
    args = parser.parse_args(argv)

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not sources:
        print("No sources specified", file=sys.stderr)
        return 1

    if args.download and args.no_download:
        print("Use only one of --download or --no-download", file=sys.stderr)
        return 1

    if args.download:
        download_previews = True
    elif args.no_download:
        download_previews = False
    else:
        download_previews = None

    return harvest_all(
        sources,
        pages=args.pages,
        page_size=args.page_size,
        download_previews=download_previews,
        query=args.query,
    )


if __name__ == "__main__":
    raise SystemExit(main())
