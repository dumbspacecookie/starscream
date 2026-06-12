"""CLI for contributing sounds to Starscream.

Usage:
    starscream-contrib init [directory]
    starscream-contrib validate manifest.json [--audio path.wav]
    starscream-contrib upload manifest.json [--api http://localhost:8000]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import httpx

from starscream.contrib.batch import discover_packages, validate_packages, write_batch_report
from starscream.contrib.submit import load_manifest
from starscream.contrib.upload_http import upload_package_http
from starscream.contrib.validator import validate_contribution

TEMPLATE = Path(__file__).parent / "templates" / "manifest.example.json"


def cmd_init(args: argparse.Namespace) -> int:
    dest = Path(args.directory)
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.json"
    if manifest_path.exists() and not args.force:
        print(f"Already exists: {manifest_path} (use --force to overwrite)", file=sys.stderr)
        return 1
    shutil.copy(TEMPLATE, manifest_path)
    print(f"Created {manifest_path}")
    print("Next steps:")
    print("  1. Record raw audio (WAV/FLAC, ≥44.1 kHz, no processing)")
    print("  2. Edit manifest.json — fill source_object, source_action, location")
    print("  3. Place audio file beside manifest (match audio_filename)")
    print("  4. Run: starscream-contrib validate manifest.json")
    print("  5. Run: starscream-contrib upload manifest.json")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    audio_path = Path(args.audio) if args.audio else Path(manifest.audio_filename)
    if not audio_path.is_absolute():
        audio_path = Path(args.manifest).parent / audio_path

    audio_bytes = audio_path.read_bytes() if audio_path.exists() else None
    if audio_bytes is None:
        print(f"Audio not found: {audio_path}", file=sys.stderr)
        return 1

    report = validate_contribution(manifest, audio_bytes, strict=not args.lenient)
    for w in report.warnings:
        print(f"WARNING: {w}")
    for e in report.errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if report.valid:
        print("Valid contribution.")
        if report.duration_s:
            print(
                f"  duration: {report.duration_s:.2f}s | "
                f"sr: {report.detected_sample_rate_hz} Hz | "
                f"ch: {report.detected_channels} | "
                f"depth: {report.detected_bit_depth}-bit"
            )
        return 0
    print("Invalid — fix errors above.", file=sys.stderr)
    return 1


def cmd_upload(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    audio_path = manifest_path.parent / manifest.audio_filename
    if not audio_path.exists():
        print(f"Audio not found: {audio_path}", file=sys.stderr)
        return 1

    report = validate_contribution(manifest, audio_path.read_bytes(), strict=not args.lenient)
    if not report.valid:
        for e in report.errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    url = args.api.rstrip("/") + "/v1/contrib/upload"
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            url,
            data={"manifest_json": manifest.model_dump_json()},
            files={"audio": (manifest.audio_filename, audio_path.read_bytes(), "audio/wav")},
        )

    if response.status_code == 201:
        body = response.json()
        rec = body["recording"]
        print(f"Uploaded: {rec['id']}")
        print(f"  title: {rec.get('title')}")
        for w in body.get("warnings", []):
            print(f"WARNING: {w}")
        return 0

    print(f"Upload failed ({response.status_code}): {response.text}", file=sys.stderr)
    return 1


def cmd_validate_batch(args: argparse.Namespace) -> int:
    root = Path(args.directory)
    packages = discover_packages(root)
    if not packages:
        print(f"No contribution packages found under {root}", file=sys.stderr)
        return 1

    validations = validate_packages(packages, strict=not args.lenient)
    valid = 0
    for v in validations:
        status = "OK" if v.report.valid else "FAIL"
        print(f"[{status}] {v.package.manifest_path}")
        for w in v.report.warnings:
            print(f"  WARNING: {w}")
        for e in v.report.errors:
            print(f"  ERROR: {e}")
        if v.report.valid:
            valid += 1

    print(f"\n{valid}/{len(validations)} valid")
    return 0 if valid == len(validations) else 1


def cmd_upload_batch(args: argparse.Namespace) -> int:
    root = Path(args.directory)
    packages = discover_packages(root)
    if not packages:
        print(f"No contribution packages found under {root}", file=sys.stderr)
        return 1

    validations = validate_packages(packages, strict=not args.lenient)
    results = []
    uploaded = failed = 0

    for v in validations:
        if not v.report.valid:
            failed += 1
            from starscream.contrib.batch import BatchUploadResult

            results.append(
                BatchUploadResult(
                    manifest_path=str(v.package.manifest_path),
                    title=v.package.manifest.title,
                    status="failed",
                    errors=v.report.errors,
                    warnings=v.report.warnings,
                )
            )
            print(f"[FAIL] {v.package.manifest_path} (validation)")
            continue

        result = upload_package_http(v.package, api_base=args.api)
        results.append(result)
        if result.status == "uploaded":
            uploaded += 1
            print(f"[OK] {result.title} → {result.recording_id}")
        else:
            failed += 1
            print(f"[FAIL] {v.package.manifest_path}")
            for e in result.errors:
                print(f"  ERROR: {e}")

    if args.report:
        write_batch_report(results, Path(args.report))

    print(f"\n{uploaded} uploaded, {failed} failed (of {len(packages)})")
    return 0 if failed == 0 else 1


def cmd_guidelines(_: argparse.Namespace) -> int:
    print("Starscream Contribution Guidelines")
    print("=" * 40)
    print()
    print("Mission: build a grounded acoustic corpus for transformers and world models.")
    print()
    print("Audio (required):")
    print("  - Raw lossless WAV, FLAC, or AIFF")
    print("  - ≥44.1 kHz sample rate, ≥16-bit depth")
    print("  - No compression, EQ, noise reduction, or normalization")
    print("  - Paired manifest.json sidecar")
    print()
    print("Metadata (required):")
    print("  - title, source_object, source_action")
    print("  - recorded_at (UTC), location (lat/lng)")
    print("  - license (CC0 or CC-BY)")
    print("  - physical_properties (for world model grounding)")
    print()
    print("Full docs: docs/CONTRIBUTING.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-contrib",
        description="Contribute grounded sounds to the Starscream corpus",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a new contribution directory")
    p_init.add_argument("directory", nargs="?", default=".", help="Target directory")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing manifest")
    p_init.set_defaults(func=cmd_init)

    p_val = sub.add_parser("validate", help="Validate manifest + audio")
    p_val.add_argument("manifest", help="Path to manifest.json")
    p_val.add_argument("--audio", help="Override audio file path")
    p_val.add_argument("--lenient", action="store_true", help="Relax physical_properties requirement")
    p_val.set_defaults(func=cmd_validate)

    p_up = sub.add_parser("upload", help="Upload to Starscream API")
    p_up.add_argument("manifest", help="Path to manifest.json")
    p_up.add_argument("--api", default="http://localhost:8000", help="API base URL")
    p_up.add_argument("--lenient", action="store_true")
    p_up.set_defaults(func=cmd_upload)

    p_vbatch = sub.add_parser("validate-batch", help="Validate all packages under a directory")
    p_vbatch.add_argument("directory", help="Root directory to scan")
    p_vbatch.add_argument("--lenient", action="store_true")
    p_vbatch.set_defaults(func=cmd_validate_batch)

    p_ubatch = sub.add_parser("upload-batch", help="Upload all valid packages under a directory")
    p_ubatch.add_argument("directory", help="Root directory to scan")
    p_ubatch.add_argument("--api", default="http://localhost:8000")
    p_ubatch.add_argument("--lenient", action="store_true")
    p_ubatch.add_argument("--report", help="Write JSON report to this path")
    p_ubatch.set_defaults(func=cmd_upload_batch)

    p_guide = sub.add_parser("guidelines", help="Print contribution guidelines")
    p_guide.set_defaults(func=cmd_guidelines)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
