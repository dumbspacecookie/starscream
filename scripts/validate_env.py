#!/usr/bin/env python3
"""Validate production environment variables before deploy. Exit 1 if required vars missing."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_ENV = REPO_ROOT / ".env.prod.example"


def required_vars_from_example(path: Path) -> list[str]:
    required: list[str] = []
    in_optional = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("# Optional"):
            in_optional = True
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped and not in_optional:
            key = stripped.split("=", 1)[0].strip()
            required.append(key)
    return required


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        values[key.strip()] = val.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production environment variables")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to .env file (default: .env in repo root)",
    )
    args = parser.parse_args()

    if not EXAMPLE_ENV.exists():
        print(f"error: {EXAMPLE_ENV} not found", file=sys.stderr)
        return 1

    required = required_vars_from_example(EXAMPLE_ENV)
    env_values = load_env_file(args.env_file) if args.env_file.exists() else {}

    def get_value(key: str) -> str:
        return os.environ.get(key, env_values.get(key, ""))

    missing = [key for key in required if not get_value(key)]

    if missing:
        print("Missing required production environment variables:", file=sys.stderr)
        for key in missing:
            print(f"  - {key}", file=sys.stderr)
        return 1

    print("All required production environment variables are set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
