#!/usr/bin/env python3
"""Validate a Starscream JSONL export sample for training readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _check_row(row: dict, line_no: int, *, metadata_only: bool) -> list[str]:
    issues: list[str] = []
    if not row.get("source_object"):
        issues.append(f"line {line_no}: missing source_object")
    if not row.get("source_action"):
        issues.append(f"line {line_no}: missing source_action")
    wm = row.get("world_model_labels") or {}
    if not wm.get("object_category"):
        issues.append(f"line {line_no}: missing world_model_labels.object_category")
    if not metadata_only and row.get("has_audio") and not row.get("audio"):
        issues.append(f"line {line_no}: has_audio=true but audio path missing")
    if not row.get("has_audio") and not row.get("external_url"):
        issues.append(f"line {line_no}: pointer row without external_url")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Starscream JSONL export rows")
    parser.add_argument("jsonl", type=Path, help="Path to dataset.jsonl or train.jsonl")
    parser.add_argument("--max-lines", type=int, default=500, help="Rows to scan")
    parser.add_argument("--metadata-only", action="store_true", help="Skip audio path checks")
    parser.add_argument("--min-grounded-pct", type=float, default=80.0)
    args = parser.parse_args(argv)

    if not args.jsonl.is_file():
        print(f"File not found: {args.jsonl}", file=sys.stderr)
        return 1

    issues: list[str] = []
    grounded = 0
    with_audio = 0
    pointers = 0
    total = 0

    for line_no, line in enumerate(args.jsonl.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        if total >= args.max_lines:
            break
        total += 1
        row = json.loads(line)
        if row.get("source_object") and row.get("source_action"):
            grounded += 1
        if row.get("has_audio"):
            with_audio += 1
        else:
            pointers += 1
        issues.extend(_check_row(row, line_no, metadata_only=args.metadata_only))

    if total == 0:
        print("No rows found", file=sys.stderr)
        return 1

    grounded_pct = 100.0 * grounded / total
    print(f"Scanned {total} rows from {args.jsonl.name}")
    print(f"  grounded (object+action): {grounded} ({grounded_pct:.1f}%)")
    print(f"  with local audio: {with_audio}")
    print(f"  pointer-only: {pointers}")

    if issues:
        print(f"\n{len(issues)} issue(s):")
        for msg in issues[:20]:
            print(f"  - {msg}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")

    if grounded_pct < args.min_grounded_pct:
        print(
            f"\nFAIL: grounded % {grounded_pct:.1f} < {args.min_grounded_pct}",
            file=sys.stderr,
        )
        return 1

    if issues:
        return 1

    print("\nOK: sample passes export checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
