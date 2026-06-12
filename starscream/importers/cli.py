"""CLI for static dataset importers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from starscream.db.session import get_session_factory
from starscream.importers.esc50 import import_esc50
from starscream.importers.fsd50k import import_fsd50k

IMPORTER_CATALOG = {
    "fsd50k": "FSD50K metadata CSV (Zenodo FSD50K.metadata/dev.csv or eval.csv)",
    "esc50": "ESC-50 meta/esc50.csv (50 classes, 2000 clips)",
}


def _print_result(result) -> int:
    print(
        f"Import complete: {result.created} created, "
        f"{result.skipped} skipped, {result.failed} failed"
    )
    for err in result.errors[:10]:
        print(f"  ERROR: {err}", file=sys.stderr)
    return 1 if result.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-import",
        description="Import static audio datasets into Starscream (local files only)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available static importers")

    fsd = sub.add_parser("fsd50k", help="Import FSD50K metadata CSV (Zenodo extract)")
    fsd.add_argument("csv", type=Path, help="Path to dev.csv or eval.csv")
    fsd.add_argument("--audio-dir", type=Path, default=None)
    fsd.add_argument("--split", choices=("dev", "eval"), default="dev")
    fsd.add_argument("--limit", type=int, default=None)
    fsd.add_argument("--no-audio", action="store_true")

    esc = sub.add_parser("esc50", help="Import ESC-50 meta/esc50.csv")
    esc.add_argument("csv", type=Path, help="Path to meta/esc50.csv")
    esc.add_argument("--audio-dir", type=Path, default=None, help="Path to audio/ folder")
    esc.add_argument("--limit", type=int, default=None)
    esc.add_argument("--no-audio", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "list":
        for name, desc in IMPORTER_CATALOG.items():
            print(f"{name}: {desc}")
        return 0

    session = get_session_factory()()
    try:
        if args.command == "fsd50k":
            result = import_fsd50k(
                session,
                args.csv,
                audio_dir=None if args.no_audio else args.audio_dir,
                split=args.split,
                limit=args.limit,
                copy_audio=not args.no_audio,
            )
        elif args.command == "esc50":
            result = import_esc50(
                session,
                args.csv,
                audio_dir=None if args.no_audio else args.audio_dir,
                limit=args.limit,
                copy_audio=not args.no_audio,
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    return _print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
