"""Export Starscream corpus for ML training.

Usage:
    starscream-export run ./output/ --format jsonl
    starscream-export run ./output/ --format parquet --split-by taxonomy
    starscream-export run ./output/ --format hf --contributions-only
    starscream-export publish ./dataset/ --repo-id user/starscream-corpus
"""

from __future__ import annotations

import argparse
from pathlib import Path

from starscream.config import get_settings
from starscream.db.session import get_session_factory
from starscream.export.builder import export_dataset
from starscream.export.publish import publish_dataset
from starscream.export.torrent import create_torrent


def cmd_torrent(args: argparse.Namespace) -> int:
    trackers = args.tracker or None
    result = create_torrent(args.export_dir, output=args.output, trackers=trackers)
    print(f"Manifest: {result.manifest_path}")
    print(f"Files: {result.file_count} ({result.total_bytes} bytes)")
    if result.torrent_path:
        print(f"Torrent: {result.torrent_path}")
    if result.magnet_uri:
        print(f"Magnet: {result.magnet_uri}")
    if not result.used_libtorrent:
        print("Note: libtorrent not installed; wrote torrent_manifest.json + magnet.txt")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    import os

    token = args.token or os.environ.get("HF_TOKEN")
    url = publish_dataset(
        args.export_dir,
        args.repo_id,
        token=token,
        private=args.private,
    )
    print(f"Published to {url}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if getattr(args, "with_audio", False) and args.no_audio:
        print("Use only one of --with-audio or --no-audio", file=__import__("sys").stderr)
        return 1

    if args.with_audio:
        download_audio = True
    elif args.no_audio:
        download_audio = False
    else:
        download_audio = not get_settings().catalog_only

    session = get_session_factory()()
    try:
        result = export_dataset(
            session,
            args.output,
            fmt=args.format,
            split_by=args.split_by,
            contributions_only=args.contributions_only,
            download_audio=download_audio,
            limit=args.limit,
        )
    finally:
        session.close()

    print(f"Exported {result.total} recordings to {result.output_dir}")
    print(f"  train: {result.train_count} | val: {result.val_count}")
    print(f"  formats: {', '.join(result.formats)}")
    print(f"  audio files: {result.audio_downloaded}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-export",
        description="Export Starscream corpus for world model / audio ML training",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Export dataset to directory")
    p_run.add_argument("output", type=Path, help="Output directory")
    p_run.add_argument(
        "--format",
        choices=["jsonl", "parquet", "hf", "all"],
        default="jsonl",
        help="Output format (default: jsonl)",
    )
    p_run.add_argument(
        "--split-by",
        choices=["country", "taxonomy", "none"],
        default="country",
        help="Deterministic train/val split key (default: country)",
    )
    p_run.add_argument(
        "--contributions-only",
        action="store_true",
        help="Export only user contributions (exclude federated records)",
    )
    p_run.add_argument(
        "--with-audio",
        action="store_true",
        help="Copy local audio into export (default off when CATALOG_ONLY=true)",
    )
    p_run.add_argument(
        "--no-audio",
        action="store_true",
        help="Metadata only, skip audio (default when CATALOG_ONLY=true)",
    )
    p_run.add_argument("--limit", type=int, help="Max recordings to export")
    p_run.set_defaults(func=cmd_run)

    p_torrent = sub.add_parser("torrent", help="Create BitTorrent snapshot of an export directory")
    p_torrent.add_argument("export_dir", type=Path, help="Exported dataset directory")
    p_torrent.add_argument(
        "--output",
        type=Path,
        help="Output .torrent path (default: <export_dir>/<name>.torrent)",
    )
    p_torrent.add_argument(
        "--tracker",
        action="append",
        dest="tracker",
        help="Tracker announce URL (repeatable; default: opentrackr)",
    )
    p_torrent.set_defaults(func=cmd_torrent)

    p_publish = sub.add_parser("publish", help="Publish export directory to Hugging Face Hub")
    p_publish.add_argument("export_dir", type=Path, help="Exported dataset directory")
    p_publish.add_argument(
        "--repo-id",
        required=True,
        help="Hugging Face dataset repo id (e.g. user/starscream-corpus)",
    )
    p_publish.add_argument("--token", help="HF token (or set HF_TOKEN env var)")
    p_publish.add_argument("--private", action="store_true", help="Create private dataset repo")
    p_publish.set_defaults(func=cmd_publish)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
