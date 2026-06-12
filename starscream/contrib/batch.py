"""Discover and process batches of contribution packages."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from starscream.contrib.schema import ContributionManifest
from starscream.contrib.submit import load_manifest
from starscream.contrib.validator import ValidationReport, validate_contribution

MANIFEST_NAME = "manifest.json"


@dataclass
class ContributionPackage:
    root: Path
    manifest_path: Path
    manifest: ContributionManifest
    audio_path: Path


@dataclass
class PackageValidation:
    package: ContributionPackage
    report: ValidationReport


@dataclass
class BatchUploadResult:
    manifest_path: str
    title: str | None
    status: str  # uploaded | skipped | failed
    recording_id: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def discover_packages(root: Path) -> list[ContributionPackage]:
    """Find contribution packages under root (each dir with manifest.json + audio)."""
    root = root.resolve()
    packages: list[ContributionPackage] = []

    if (root / MANIFEST_NAME).exists():
        candidates = [root]
    else:
        candidates = [p.parent for p in root.rglob(MANIFEST_NAME)]

    seen: set[Path] = set()
    for directory in sorted(candidates):
        manifest_path = directory / MANIFEST_NAME
        if manifest_path in seen or not manifest_path.exists():
            continue
        seen.add(manifest_path)

        manifest = load_manifest(manifest_path)
        audio_path = directory / manifest.audio_filename
        packages.append(
            ContributionPackage(
                root=directory,
                manifest_path=manifest_path,
                manifest=manifest,
                audio_path=audio_path,
            )
        )

    return packages


def validate_packages(
    packages: list[ContributionPackage],
    *,
    strict: bool = True,
) -> list[PackageValidation]:
    results: list[PackageValidation] = []
    for pkg in packages:
        audio_bytes = pkg.audio_path.read_bytes() if pkg.audio_path.exists() else None
        report = validate_contribution(pkg.manifest, audio_bytes, strict=strict)
        results.append(PackageValidation(package=pkg, report=report))
    return results


def packages_from_zip(zip_bytes: bytes) -> tuple[list[ContributionPackage], TemporaryDirectory]:
    """Extract ZIP and discover packages. Returns (packages, temp_dir_handle)."""
    tmp = TemporaryDirectory(prefix="starscream-batch-")
    root = Path(tmp.name)
    with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as zf:
        zf.extractall(root)
    return discover_packages(root), tmp

def write_batch_report(results: list[BatchUploadResult], path: Path) -> None:
    path.write_text(
        json.dumps([r.__dict__ for r in results], indent=2),
        encoding="utf-8",
    )
