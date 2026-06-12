#!/usr/bin/env python3
"""Run a named harvest profile from config/harvest_profiles.json.

Supports simple profiles (sources list) and job-based profiles (per-source queries).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = REPO_ROOT / "config" / "harvest_profiles.json"


def _run_job(job: dict, download: bool) -> int:
    from starscream.jobs.harvest_all import harvest_all

    source = job["source"]
    return harvest_all(
        [source],
        pages=int(job.get("pages", 1)),
        page_size=int(job.get("page_size", 50)),
        download_previews=download,
        query=job.get("query"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Starscream harvest profile")
    parser.add_argument(
        "profile",
        nargs="?",
        default="metadata_light",
        help="Profile name from config/harvest_profiles.json",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available profile names",
    )
    args = parser.parse_args(argv)

    if not PROFILES_PATH.exists():
        print(f"Profiles file not found: {PROFILES_PATH}", file=sys.stderr)
        return 1

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if args.list:
        for name in profiles:
            print(name)
        return 0

    if args.profile not in profiles:
        print(f"Unknown profile: {args.profile}", file=sys.stderr)
        print(f"Available: {', '.join(profiles)}", file=sys.stderr)
        return 1

    cfg = profiles[args.profile]
    download = bool(cfg.get("download", False))

    if jobs := cfg.get("jobs"):
        print(f"Profile {args.profile!r}: {len(jobs)} job(s), download={download}")
        exit_code = 0
        for i, job in enumerate(jobs, start=1):
            label = job.get("query") or job["source"]
            print(f"\n--- Job {i}/{len(jobs)}: {job['source']} ({label}) ---")
            rc = _run_job(job, download)
            exit_code = max(exit_code, rc)
        return exit_code

    sources = [s.strip() for s in str(cfg.get("sources", "")).split(",") if s.strip()]
    pages = int(cfg.get("pages", 1))
    page_size = int(cfg.get("page_size", 50))

    print(
        f"Profile {args.profile!r}: sources={sources} pages={pages} "
        f"page_size={page_size} download={download}"
    )

    from starscream.jobs.harvest_all import harvest_all

    return harvest_all(
        sources,
        pages=pages,
        page_size=page_size,
        download_previews=download,
        query=cfg.get("query"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
