#!/usr/bin/env python3
"""Create GitHub issues from docs/ROADMAP.md tiers.

Usage:
    python scripts/create_roadmap_issues.py --dry-run          # print plan
    python scripts/create_roadmap_issues.py --export           # write docs/GITHUB_ISSUES.md
    python scripts/create_roadmap_issues.py --create           # requires `gh` + git remote

Labels created if missing: tier-0 … tier-8, area-platform, area-tests, area-federation,
area-importers, area-corpus, area-process.

Milestones: v0.1, v0.2
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = REPO_ROOT / "docs" / "GITHUB_ISSUES.md"

LABELS = [
    "tier-0",
    "tier-1",
    "tier-2",
    "tier-3",
    "tier-4",
    "tier-5",
    "tier-6",
    "tier-7",
    "tier-8",
    "area-platform",
    "area-tests",
    "area-federation",
    "area-importers",
    "area-corpus",
    "area-process",
]

MILESTONES = {
    "v0.1": "Trust, CI, core E2E, corpus proof (Tiers 0–2, 7, 8)",
    "v0.2": "Collectors, importers, scale, integrations (Tiers 3–6)",
}


@dataclass(frozen=True)
class RoadmapIssue:
    roadmap_id: str
    title: str
    body: str
    tier: str
    milestone: str
    labels: tuple[str, ...]


ISSUES: list[RoadmapIssue] = [
    # --- Tier 0 ---
    RoadmapIssue(
        "0.1",
        "[Tier 0] Commit untracked core modules",
        """## Roadmap 0.1

Commit all foundational work still sitting untracked in the working tree.

### Checklist
- [ ] `starscream/api/auth.py`, `middleware.py`, `peer_review.py`
- [ ] `starscream/api/routes/admin.py`, `contributors.py`, `reviews.py`
- [ ] `starscream/jobs/` package
- [ ] `starscream/federation/inaturalist.py`
- [ ] `starscream/static/explore.html`, `export/publish.py`
- [ ] `alembic/versions/004_quality_trust.py` and any other pending migrations
- [ ] Tests: `test_inaturalist.py`, `test_quality_trust.py`, `test_explore_ui.py`

### Exit
`git status` clean except intentional WIP.

Ref: [docs/ROADMAP.md](../docs/ROADMAP.md#tier-0--must-happen-before-done)
""",
        "tier-0",
        "v0.1",
        ("tier-0", "area-process"),
    ),
    RoadmapIssue(
        "0.2",
        "[Tier 0] Green CI integration job on GitHub",
        """## Roadmap 0.2

Push a branch/PR and confirm the **integration** job passes on GitHub Actions.

### Checklist
- [ ] `pip install -e ".[dev]"` includes testcontainers + fakeredis
- [ ] Job runs `pytest tests/test_e2e.py -m integration` with Docker
- [ ] Screenshot or link to green run in PR

Ref: `.github/workflows/ci.yml`
""",
        "tier-0",
        "v0.1",
        ("tier-0", "area-tests", "area-process"),
    ),
    RoadmapIssue(
        "0.3",
        "[Tier 0] Witness smoke E2E on real Docker stack",
        """## Roadmap 0.3

Human-verified end-to-end run (not just test harness locally).

```powershell
docker compose up -d
pip install -e ".[dev,export]"
alembic upgrade head
python -m starscream.seed
.\\scripts\\smoke_e2e.ps1
```

### Exit
Smoke script completes; note run in CHANGELOG or release notes.
""",
        "tier-0",
        "v0.1",
        ("tier-0", "area-tests", "area-platform"),
    ),
    RoadmapIssue(
        "0.4",
        "[Tier 0] Freeze v0.1 scope - stop expanding surface",
        """## Roadmap 0.4

Lock [V0.1_SCOPE.md](../docs/V0.1_SCOPE.md) until Tier 0 complete.

### Rules until v0.1 tag
- No new experimental features without explicit scope amendment
- New connectors/importers only after corpus proof (Tier 7)

### Deliverable
- [ ] Scope doc updated with explicit **out of scope** list
- [ ] BACKLOG.md points to ROADMAP.md
""",
        "tier-0",
        "v0.1",
        ("tier-0", "area-process"),
    ),
    RoadmapIssue(
        "0.5",
        "[Tier 0] Corpus proof: harvest -> import -> export -> validate",
        """## Roadmap 0.5

First real catalog on dedicated machine. See [PHASE2_RUNBOOK.md](../docs/PHASE2_RUNBOOK.md).

### Steps
1. `python scripts/run_harvest_profile.py metadata_light`
2. `starscream-import esc50` + `starscream-import fsd50k` (metadata sample)
3. `starscream-export run ./corpus/ --format jsonl --no-audio`
4. `python scripts/validate_export_sample.py ./corpus/dataset.jsonl`
5. `python scripts/corpus_report.py`

### Exit
Validated export artifact checked in or attached to release notes.
""",
        "tier-0",
        "v0.1",
        ("tier-0", "area-corpus", "area-federation", "area-importers"),
    ),
    # --- Tier 1 (grouped epics) ---
    RoadmapIssue(
        "1-ops",
        "[Tier 1] Platform reliability & ops hardening",
        """## Roadmap Tier 1 — Reliability

- [ ] **1.1** Prod compose smoke in CI
- [ ] **1.2** Entrypoint migrations + seed on prod image boot
- [ ] **1.3** Redis upload job E2E (`?async=true`)
- [ ] **1.4** Harvest run failure alerting / `detail` JSON visibility
- [ ] **1.5** Connection timeouts on all DB/Redis/S3 scripts
- [ ] **1.6** Graceful degradation matrix — doc + tests
- [ ] **1.7** Postgres + MinIO backup/restore runbook
""",
        "tier-1",
        "v0.1",
        ("tier-1", "area-platform"),
    ),
    RoadmapIssue(
        "1-sec",
        "[Tier 1] Security, auth & abuse hardening",
        """## Roadmap Tier 1 — Security

- [ ] **1.8** Auth integration tests (register, upload, admin)
- [ ] **1.9** Rate limit E2E with Redis in integration job
- [ ] **1.10** Upload hardening regression tests
- [ ] **1.11** Secrets hygiene + complete `.env.example`
""",
        "tier-1",
        "v0.1",
        ("tier-1", "area-platform", "area-tests"),
    ),
    RoadmapIssue(
        "1-data",
        "[Tier 1] Data integrity & license enforcement",
        """## Roadmap Tier 1 — Data integrity

- [ ] **1.12** Dedup E2E variants (cross-source, pointer-only, re-ingest)
- [ ] **1.13** Meilisearch reindex after bulk harvest/import
- [ ] **1.14** Alembic — no forked heads; all migrations committed
- [ ] **1.15** License audit — CC-BY-NC never stores audio bytes
""",
        "tier-1",
        "v0.1",
        ("tier-1", "area-platform", "area-tests"),
    ),
    # --- Tier 2 ---
    RoadmapIssue(
        "2-e2e",
        "[Tier 2] Expand integration / E2E test coverage",
        """## Roadmap Tier 2 — E2E targets

- [ ] **2.1** Federation harvest E2E (HTTP fixtures → DB → search)
- [ ] **2.2** FSD50K/ESC-50 import E2E
- [ ] **2.3** Export E2E (`test_e2e_export.py` green)
- [ ] **2.4** Background upload job E2E (Redis worker)
- [ ] **2.5** Spatial + filter combo tests
- [ ] **2.6** Harvest scheduler → `HarvestRun` + detail
- [ ] **2.7** Peer review flow E2E
- [ ] **2.8** MQTT ingest E2E
- [ ] **2.9** GraphQL smoke (if in scope)
- [ ] **2.10** Chaos: Meili down, S3 timeout, harvest page 500
""",
        "tier-2",
        "v0.1",
        ("tier-2", "area-tests"),
    ),
    RoadmapIssue(
        "2-ci",
        "[Tier 2] CI hardening for integration tests",
        """## Roadmap Tier 2 — CI

- [ ] **2.11** Integration job includes `test_e2e_export.py`
- [ ] **2.12** Pin testcontainer image digests
- [ ] **2.13** Coverage floor on ingest, dedup, export, harvest
- [ ] **2.14** Nightly harvest profile workflow (dedicated runner)
""",
        "tier-2",
        "v0.1",
        ("tier-2", "area-tests", "area-process"),
    ),
    # --- Tier 3 ---
    RoadmapIssue(
        "3-existing",
        "[Tier 3] Prove existing federation collectors at scale",
        """## Existing connectors

`freesound`, `xeno-canto`, `inaturalist`, `internet-archive`, `noaa`, `nasa`

- [ ] **3.1** Run `metadata_light` harvest profile on dedicated machine
- [ ] **3.2** Per-connector metrics in admin API
- [ ] **3.3** Incremental harvest checkpoints per source
- [ ] **3.4** Freesound OAuth for full-quality audio
- [ ] **3.5** iNaturalist backoff + pagination caps
""",
        "tier-3",
        "v0.2",
        ("tier-3", "area-federation"),
    ),
    RoadmapIssue(
        "3-new",
        "[Tier 3] New federation collector (one vertical slice)",
        """## v0.2+ — pick ONE per sprint

Each requires: connector + seed + harvest profile + grounding + license policy + fixture test.

Candidates:
- Macaulay Library (Cornell)
- Wikimedia Commons
- Zenodo/Figshare DOI harvester
- GBIF media links
- OpenSLR / Common Voice

### Definition of done
- [ ] Connector merged with integration test (recorded fixtures)
- [ ] Documented in FEDERATION.md
- [ ] Harvest profile in `config/harvest_profiles.json`
""",
        "tier-3",
        "v0.2",
        ("tier-3", "area-federation"),
    ),
    # --- Tier 4 ---
    RoadmapIssue(
        "4-infra",
        "[Tier 4] Static importer infrastructure",
        """## Roadmap Tier 4 — Importer platform

Done: FSD50K, ESC-50

- [ ] **4.1** Generic manifest importer (JSONL/CSV)
- [ ] **4.2** Import validation CLI
- [ ] **4.3** Batch re-ingest (grounding updates)
- [ ] **4.4** Per-dataset audio policy (copy/pointer/transcode)
""",
        "tier-4",
        "v0.2",
        ("tier-4", "area-importers"),
    ),
    RoadmapIssue(
        "4-datasets",
        "[Tier 4] New static dataset importer (one vertical slice)",
        """## Candidates (pick one)

UrbanSound8K, NSynth, BirdCLEF/DCASE, AudioSet metadata (pointer-only), WavCaps/Clotho

### Definition of done
- [ ] `starscream-import <name>` CLI
- [ ] Seed source in bootstrap
- [ ] Import profile in `config/import_profiles.json`
- [ ] Tests + IMPORTERS.md section
""",
        "tier-4",
        "v0.2",
        ("tier-4", "area-importers"),
    ),
    # --- Tier 5 ---
    RoadmapIssue(
        "5-integrations",
        "[Tier 5] Service integration hardening",
        """## Per-service targets

| Service | Action |
|---------|--------|
| Redis | Required in multi-worker prod; job E2E |
| MQTT | testcontainers broker + subscriber E2E |
| HF publish | test repo publish E2E |
| GraphQL | cut or commit with e2e |
| BitTorrent | cut or one e2e |
| WebSocket | load + reconnect tests |
| Enrichment APIs | circuit breaker + cache + metrics |
| ML `[ml]` | ONNX path for Python 3.13+ |
| Observability | OpenTelemetry + Prometheus dashboards |

**No second primary DB until Tiers 0–7 green.**
""",
        "tier-5",
        "v0.2",
        ("tier-5", "area-platform"),
    ),
    # --- Tier 6 ---
    RoadmapIssue(
        "6-scale",
        "[Tier 6] Data model & scale (corpus > ~100k)",
        """## Roadmap Tier 6

- [ ] **6.1** Taxonomy normalization table
- [ ] **6.2** Annotation / event layer
- [ ] **6.3** Provenance graph (source → harvest_run → recording)
- [ ] **6.4** Quality/trust scores wired (`004_quality_trust`)
- [ ] **6.5** Postgres full-text fallback when Meili down
- [ ] **6.6** Cold archival tier for FLAC
- [ ] **6.7** Analytics DB (scale only)
- [ ] **6.8** Vector index for similar sounds
""",
        "tier-6",
        "v0.2",
        ("tier-6", "area-platform"),
    ),
    # --- Tier 7 ---
    RoadmapIssue(
        "7.1",
        "[Tier 7] Metadata harvest (`metadata_light`)",
        "Run `python scripts/run_harvest_profile.py metadata_light` on dedicated machine. Verify with `corpus_report.py`.",
        "tier-7",
        "v0.1",
        ("tier-7", "area-corpus", "area-federation"),
    ),
    RoadmapIssue(
        "7.2",
        "[Tier 7] Static dataset import (FSD50K + ESC-50)",
        "Import metadata samples per [IMPORTERS.md](../docs/IMPORTERS.md) and [PHASE2_RUNBOOK.md](../docs/PHASE2_RUNBOOK.md).",
        "tier-7",
        "v0.1",
        ("tier-7", "area-corpus", "area-importers"),
    ),
    RoadmapIssue(
        "7.3",
        "[Tier 7] Overnight audio harvest (`catalog_build`)",
        "Run with enrichment disabled in `.env`. Profile: `config/harvest_profiles.json` → `catalog_build`.",
        "tier-7",
        "v0.1",
        ("tier-7", "area-corpus", "area-federation"),
    ),
    RoadmapIssue(
        "7.4",
        "[Tier 7] JSONL export + validate_export_sample",
        "Export corpus and pass `scripts/validate_export_sample.py` at ≥80% grounded rows.",
        "tier-7",
        "v0.1",
        ("tier-7", "area-corpus"),
    ),
    RoadmapIssue(
        "7.5-7.8",
        "[Tier 7] Catalog polish",
        """- [ ] **7.5** Export schema semver in `export_meta.json`
- [ ] **7.6** Training license filters documented ([TRAINING_EXPORT.md](../docs/TRAINING_EXPORT.md))
- [ ] **7.7** Richer `world_model_labels` for top taxonomies
- [ ] **7.8** Public sample corpus tarball (CC0/CC-BY)
""",
        "tier-7",
        "v0.1",
        ("tier-7", "area-corpus"),
    ),
    # --- Tier 8 ---
    RoadmapIssue(
        "8-process",
        "[Tier 8] Process & governance",
        """## Roadmap Tier 8

- [ ] **8.1** PR = vertical slice (code + tests + migration + docs, committed)
- [ ] **8.2** Connector definition-of-done in FEDERATION.md
- [ ] **8.3** CHANGELOG + semver; tag v0.1 after Tier 0
- [ ] **8.4** CI matrix Python 3.11 + 3.12
- [ ] **8.5** Enforce RESOURCE_GUIDE — heavy work on dedicated machines
- [ ] **8.6** Sync BACKLOG.md ↔ ROADMAP.md
""",
        "tier-8",
        "v0.1",
        ("tier-8", "area-process"),
    ),
]


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _run_gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def export_markdown() -> str:
    lines = [
        "# GitHub issues export",
        "",
        "Generated by `python scripts/create_roadmap_issues.py --export`.",
        "Create on GitHub when `gh` is installed and a remote is configured:",
        "",
        "```bash",
        "gh auth login",
        "git remote add origin <your-repo-url>  # if missing",
        "python scripts/create_roadmap_issues.py --create",
        "```",
        "",
        f"**{len(ISSUES)} issues** across tiers 0–8.",
        "",
    ]
    for issue in ISSUES:
        label_str = ", ".join(f"`{label}`" for label in issue.labels)
        lines.extend(
            [
                "---",
                "",
                f"## {issue.title}",
                "",
                f"- **Roadmap ID:** {issue.roadmap_id}",
                f"- **Milestone:** {issue.milestone}",
                f"- **Labels:** {label_str}",
                "",
                issue.body,
                "",
            ]
        )
    return "\n".join(lines)


def ensure_labels() -> None:
    for label in LABELS:
        color = "0e8a16" if label.startswith("tier-") else "1d76db"
        _run_gh(
            ["label", "create", label, "--color", color, "--force"],
            check=False,
        )


def ensure_milestones() -> dict[str, str]:
    existing: dict[str, str] = {}
    result = _run_gh(["api", "repos/{owner}/{repo}/milestones", "--paginate"], check=False)
    if result.returncode == 0 and result.stdout.strip():
        for row in json.loads(result.stdout):
            existing[row["title"]] = str(row["number"])

    for title, description in MILESTONES.items():
        if title in existing:
            continue
        result = _run_gh(
            [
                "api",
                "repos/{owner}/{repo}/milestones",
                "-f",
                f"title={title}",
                "-f",
                f"description={description}",
            ],
            check=False,
        )
        if result.returncode == 0:
            existing[title] = str(json.loads(result.stdout)["number"])
    return existing


def create_issues(*, dry_run: bool) -> list[str]:
    urls: list[str] = []
    milestones: dict[str, str] = {}
    if not dry_run:
        milestones = ensure_milestones()

    for issue in ISSUES:
        cmd = [
            "issue",
            "create",
            "--title",
            issue.title,
            "--body",
            issue.body,
            "--label",
            ",".join(issue.labels),
        ]
        if issue.milestone in milestones:
            cmd.extend(["--milestone", issue.milestone])

        if dry_run:
            print(f"[dry-run] {issue.roadmap_id}: {issue.title} [{issue.milestone}]")
            continue

        result = _run_gh(cmd)
        url = result.stdout.strip()
        urls.append(url)
        print(url)

    return urls


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create GitHub issues from Starscream roadmap")
    parser.add_argument("--dry-run", action="store_true", help="Print issue creation plan")
    parser.add_argument("--export", action="store_true", help="Write docs/GITHUB_ISSUES.md")
    parser.add_argument("--create", action="store_true", help="Create issues via gh CLI")
    args = parser.parse_args(argv)

    if args.export or (not args.dry_run and not args.create):
        EXPORT_PATH.write_text(export_markdown(), encoding="utf-8")
        print(f"Wrote {EXPORT_PATH}")
        if not args.create and not args.dry_run:
            return 0

    if args.dry_run:
        create_issues(dry_run=True)
        return 0

    if args.create:
        if not _gh_available():
            print(
                "Error: `gh` CLI not found. Install: https://cli.github.com/\n"
                f"Issue bodies are in {EXPORT_PATH}",
                file=sys.stderr,
            )
            return 1
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if remote.returncode != 0:
            print(
                "Error: no git remote `origin`. Add remote then re-run:\n"
                "  git remote add origin https://github.com/<owner>/starscream.git",
                file=sys.stderr,
            )
            return 1
        ensure_labels()
        create_issues(dry_run=False)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
