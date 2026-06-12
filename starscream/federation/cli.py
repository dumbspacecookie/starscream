"""Harvest federated archives into Starscream.

Usage:
    starscream-harvest freesound --pages 2 --page-size 50
"""

from __future__ import annotations

import argparse
import sys

from starscream.db.session import get_session_factory
from starscream.federation.harvest import harvest_source_sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-harvest",
        description="Harvest external sound archives into Starscream",
    )
    parser.add_argument(
        "source",
        choices=[
            "freesound",
            "xeno-canto",
            "inaturalist",
            "internet-archive",
            "noaa",
            "nasa",
        ],
        help="Archive to harvest",
    )
    parser.add_argument("--pages", type=int, default=1, help="Pages to fetch")
    parser.add_argument("--page-size", type=int, default=50, help="Records per page")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download preview audio when license permits",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Metadata only (default when CATALOG_ONLY=true)",
    )
    args = parser.parse_args(argv)

    if args.download and args.no_download:
        print("Use only one of --download or --no-download", file=sys.stderr)
        return 1

    if args.download:
        download_previews = True
    elif args.no_download:
        download_previews = False
    else:
        download_previews = None

    session = get_session_factory()()
    try:
        result = harvest_source_sync(
            session,
            args.source,
            pages=args.pages,
            page_size=args.page_size,
            download_previews=download_previews,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        session.close()

    print(f"Harvest complete: {result.created} created, {result.skipped} skipped, {result.failed} failed")
    for err in result.errors[:10]:
        print(f"  ERROR: {err}", file=sys.stderr)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
