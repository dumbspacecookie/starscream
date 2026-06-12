"""Scheduled federation harvest runner.

Usage:
    python -m starscream.jobs.scheduler run-once
    python -m starscream.jobs.scheduler daemon --interval-hours 24
"""

from __future__ import annotations

import argparse
import sys
import time

import schedule

from starscream.federation.harvest import CONNECTORS
from starscream.jobs.harvest_all import DEFAULT_SOURCES, harvest_all

DEFAULT_INTERVAL_HOURS = 24
POLL_INTERVAL_S = 60


def run_scheduled_harvest(
    sources: list[str],
    *,
    pages: int = 1,
    page_size: int = 50,
    download_previews: bool = True,
) -> int:
    return harvest_all(
        sources,
        pages=pages,
        page_size=page_size,
        download_previews=download_previews,
    )


def run_daemon(
    sources: list[str],
    *,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    pages: int = 1,
    page_size: int = 50,
    download_previews: bool = True,
    poll_interval_s: int = POLL_INTERVAL_S,
    stop_after: int | None = None,
) -> int:
    exit_code = 0
    runs = 0

    def job() -> None:
        nonlocal exit_code, runs
        code = run_scheduled_harvest(
            sources,
            pages=pages,
            page_size=page_size,
            download_previews=download_previews,
        )
        if code:
            exit_code = code
        runs += 1

    schedule.every(interval_hours).hours.do(job)
    job()

    while stop_after is None or runs < stop_after:
        schedule.run_pending()
        time.sleep(poll_interval_s)

    return exit_code


def _add_harvest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"Comma-separated source slugs (default: {','.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument("--pages", type=int, default=1, help="Pages per source")
    parser.add_argument("--page-size", type=int, default=50, help="Records per page")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Metadata only (no preview audio)",
    )


def _parse_sources(raw: str) -> list[str]:
    sources = [s.strip() for s in raw.split(",") if s.strip()]
    if not sources:
        raise ValueError("No sources specified")
    return sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run scheduled federation harvests for Starscream",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once_parser = subparsers.add_parser(
        "run-once",
        help="Run one harvest cycle and exit",
    )
    _add_harvest_args(run_once_parser)

    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Run harvests on a repeating schedule",
    )
    _add_harvest_args(daemon_parser)
    daemon_parser.add_argument(
        "--interval-hours",
        type=int,
        default=DEFAULT_INTERVAL_HOURS,
        help=f"Hours between harvest cycles (default: {DEFAULT_INTERVAL_HOURS})",
    )

    args = parser.parse_args(argv)

    try:
        sources = _parse_sources(args.sources)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    unknown = [slug for slug in sources if slug not in CONNECTORS]
    if unknown:
        print(f"Unknown sources: {unknown}. Available: {list(CONNECTORS)}", file=sys.stderr)
        return 1

    harvest_kwargs = {
        "pages": args.pages,
        "page_size": args.page_size,
        "download_previews": not args.no_download,
    }

    if args.command == "run-once":
        return run_scheduled_harvest(sources, **harvest_kwargs)

    return run_daemon(
        sources,
        interval_hours=args.interval_hours,
        **harvest_kwargs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
