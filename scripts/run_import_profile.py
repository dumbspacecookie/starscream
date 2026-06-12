#!/usr/bin/env python3
"""Run a named static import profile from config/import_profiles.json.

Edit CSV paths in the profile (replace CHANGE_ME) before running on a dedicated machine.
Does not download datasets — only ingests local files into Postgres.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = REPO_ROOT / "config" / "import_profiles.json"

IMPORTERS = {
    "fsd50k": "starscream.importers.fsd50k:import_fsd50k",
    "esc50": "starscream.importers.esc50:import_esc50",
}


def _load_importer(name: str):
    if name not in IMPORTERS:
        raise ValueError(f"Unknown importer: {name}")
    module_path, func_name = IMPORTERS[name].split(":")
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


def _parse_entry_args(args: list[str]) -> dict:
    out: dict = {}
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--no-audio":
            out["copy_audio"] = False
            i += 1
            continue
        if token == "--limit" and i + 1 < len(args):
            out["limit"] = int(args[i + 1])
            i += 2
            continue
        if token == "--split" and i + 1 < len(args):
            out["split"] = args[i + 1]
            i += 2
            continue
        if token == "--audio-dir" and i + 1 < len(args):
            out["audio_dir"] = Path(args[i + 1])
            i += 2
            continue
        raise ValueError(f"Unsupported import arg: {token}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Starscream static import profile")
    parser.add_argument("profile", nargs="?", help="Profile name from config/import_profiles.json")
    parser.add_argument("--list", action="store_true", help="List profile names")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without importing")
    args = parser.parse_args(argv)

    if not PROFILES_PATH.exists():
        print(f"Profiles file not found: {PROFILES_PATH}", file=sys.stderr)
        return 1

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if args.list:
        for name, cfg in profiles.items():
            desc = cfg.get("description", "")
            print(f"{name}: {desc}" if desc else name)
        return 0

    if not args.profile or args.profile not in profiles:
        print(f"Unknown profile: {args.profile}", file=sys.stderr)
        print(f"Available: {', '.join(profiles)}", file=sys.stderr)
        return 1

    cfg = profiles[args.profile]
    entries = cfg.get("imports", [])
    if not entries:
        print("Profile has no imports", file=sys.stderr)
        return 1

    from starscream.db.session import get_session_factory

    session = get_session_factory()()
    total_created = total_skipped = total_failed = 0
    try:
        for entry in entries:
            importer_name = entry["importer"]
            csv_path = Path(entry["csv"])
            if "CHANGE_ME" in str(csv_path):
                print(f"Skipping {importer_name}: edit csv path in profile ({csv_path})", file=sys.stderr)
                continue
            if not csv_path.exists():
                print(f"CSV not found: {csv_path}", file=sys.stderr)
                return 1

            opts = _parse_entry_args(entry.get("args", []))
            copy_audio = opts.pop("copy_audio", True)
            audio_dir = opts.pop("audio_dir", None)

            print(f"Importing {importer_name} from {csv_path} ...")
            if args.dry_run:
                continue

            fn = _load_importer(importer_name)
            if importer_name == "fsd50k":
                result = fn(
                    session,
                    csv_path,
                    audio_dir=None if not copy_audio else audio_dir,
                    copy_audio=copy_audio,
                    **opts,
                )
            else:
                result = fn(
                    session,
                    csv_path,
                    audio_dir=None if not copy_audio else audio_dir,
                    copy_audio=copy_audio,
                    **opts,
                )
            total_created += result.created
            total_skipped += result.skipped
            total_failed += result.failed
            print(
                f"  {result.created} created, {result.skipped} skipped, {result.failed} failed"
            )
            for err in result.errors[:5]:
                print(f"  ERROR: {err}", file=sys.stderr)
    finally:
        session.close()

    if args.dry_run:
        print("Dry run complete.")
        return 0

    print(
        f"Profile done: {total_created} created, {total_skipped} skipped, {total_failed} failed"
    )
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
