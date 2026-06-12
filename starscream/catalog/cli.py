"""CLI for offline catalog search — no Docker, no server."""

from __future__ import annotations

import argparse
import json
import sys

from starscream.catalog.reader import Catalog, find_catalog_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-catalog",
        description="Search the Starscream sound catalog (JSONL, pointer-only)",
    )
    parser.add_argument(
        "--catalog",
        type=str,
        default=None,
        help="Path to dataset.jsonl (default: corpus/dataset.jsonl or STARSCREAM_CATALOG_PATH)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Keyword search")
    p_search.add_argument("query", help="Search terms")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--source", dest="source_slug", default=None)
    p_search.add_argument("--license", default=None)
    p_search.add_argument("--taxonomy", dest="taxonomy_code", default=None)
    p_search.add_argument(
        "--redistributable",
        action="store_true",
        help="CC0 / CC-BY / public-domain rows only",
    )
    p_search.add_argument("--json", action="store_true", help="Full JSON output")

    p_get = sub.add_parser("get", help="Get one row by UUID")
    p_get.add_argument("id")
    p_get.add_argument("--json", action="store_true")

    sub.add_parser("stats", help="Catalog summary")
    sub.add_parser("path", help="Print resolved catalog file path")

    args = parser.parse_args(argv)

    try:
        if args.command == "path":
            print(find_catalog_path(args.catalog))
            return 0

        catalog = Catalog.load(args.catalog)

        if args.command == "stats":
            print(json.dumps(catalog.stats(), indent=2))
            return 0

        if args.command == "get":
            row = catalog.get(args.id)
            if not row:
                print(f"Not found: {args.id}", file=sys.stderr)
                return 1
            out = row if args.json else catalog.compact(row)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        if args.command == "search":
            rows = catalog.search(
                args.query,
                limit=args.limit,
                source_slug=args.source_slug,
                license=args.license,
                taxonomy_code=args.taxonomy_code,
                redistributable_only=args.redistributable,
            )
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                print(json.dumps([catalog.compact(r) for r in rows], indent=2, ensure_ascii=False))
            return 0

    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
