"""Generate ML model cards for models trained on Starscream exports.

Usage:
    starscream-model-card generate --export-dir ./dataset/ --model-name my-model --output MODEL_CARD.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from starscream.governance.policies import GOVERNANCE_SUMMARY

STARSCREAM_CORPUS_URL = "https://data.starscream.org"
STARSCREAM_PROJECT_URL = "https://starscream.org"


def _load_export_meta(export_dir: Path) -> dict[str, Any]:
    meta_path = export_dir / "export_meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Missing export_meta.json in {export_dir}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _iter_dataset_rows(export_dir: Path) -> list[dict[str, Any]]:
    dataset_jsonl = export_dir / "dataset.jsonl"
    if dataset_jsonl.is_file():
        return _read_jsonl(dataset_jsonl)

    rows: list[dict[str, Any]] = []
    for name in ("train.jsonl", "val.jsonl"):
        path = export_dir / name
        if path.is_file():
            rows.extend(_read_jsonl(path))
    if not rows:
        raise FileNotFoundError(
            f"No dataset.jsonl or train/val JSONL found in {export_dir}"
        )
    return rows


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def analyze_export(export_dir: Path) -> dict[str, Any]:
    """Collect export stats, contributor counts, and license breakdown."""
    meta = _load_export_meta(export_dir)
    rows = _iter_dataset_rows(export_dir)

    contributor_ids: set[str] = set()
    contributor_names: set[str] = set()
    licenses: Counter[str] = Counter()

    for row in rows:
        license_value = row.get("license") or "unknown"
        licenses[str(license_value)] += 1

        contributor_id = row.get("contributor_id")
        if contributor_id:
            contributor_ids.add(str(contributor_id))

        contributor_name = row.get("contributor_name")
        if contributor_name:
            contributor_names.add(str(contributor_name))

    return {
        "export_meta": meta,
        "row_count": len(rows),
        "unique_contributors": len(contributor_ids),
        "unique_contributor_names": len(contributor_names),
        "license_breakdown": dict(sorted(licenses.items())),
    }


def build_citation_text(model_name: str) -> dict[str, str]:
    """Return BibTeX and plain-text citation blocks for the Starscream corpus."""
    bibtex = f"""@misc{{starscream_corpus_{model_name.replace('-', '_')},
  title        = {{Starscream Open Acoustic Corpus}},
  author       = {{Starscream Foundation and Contributors}},
  year         = {{2024}},
  howpublished = {{\\url{{{STARSCREAM_CORPUS_URL}}}}},
  note         = {{Training data for model {model_name}}}
}}"""

    plain = (
        f"Starscream Foundation and Contributors. "
        f"Starscream Open Acoustic Corpus. {STARSCREAM_CORPUS_URL}. "
        f"Used to train {model_name}."
    )

    return {"bibtex": bibtex, "plain_text": plain}


def render_model_card(
    *,
    model_name: str,
    export_dir: Path,
    analysis: dict[str, Any],
) -> str:
    """Render a Hugging Face-style model card in Markdown."""
    meta = analysis["export_meta"]
    citation = build_citation_text(model_name)
    ai_clause = GOVERNANCE_SUMMARY["ai_training_clause"]

    license_lines = "\n".join(
        f"| {license_name} | {count} |"
        for license_name, count in analysis["license_breakdown"].items()
    )

    formats = ", ".join(meta.get("formats") or [])
    split_by = meta.get("split_by", "unknown")

    return f"""---
language: en
license: cc0-1.0
tags:
  - starscream
  - audio
  - world-models
---

# {model_name}

Model trained on the [Starscream Open Acoustic Corpus]({STARSCREAM_CORPUS_URL}).

## Training data

| Field | Value |
|---|---|
| Export directory | `{export_dir}` |
| Recordings (export meta) | {meta.get("total", analysis["row_count"])} |
| Train split | {meta.get("train", "—")} |
| Validation split | {meta.get("val", "—")} |
| Split key | {split_by} |
| Formats | {formats or "—"} |
| Audio files downloaded | {meta.get("audio_downloaded", "—")} |
| Unique contributors | {analysis["unique_contributors"]} |

### License breakdown

| License | Recordings |
|---|---|
{license_lines}

Per-row licenses are CC0 or CC-BY per [Starscream governance]({STARSCREAM_PROJECT_URL}/docs/GOVERNANCE.md).

## Attribution

{ai_clause["summary"]} {ai_clause["attribution"]}

Include `contributor_id` and `contributor_name` from training metadata when reporting results.

## Citation

### Plain text

{citation["plain_text"]}

### BibTeX

```bibtex
{citation["bibtex"]}
```

## Governance

This model card satisfies the Starscream AI training clause. See
[{STARSCREAM_PROJECT_URL}/docs/MODEL_CARD.md]({STARSCREAM_PROJECT_URL}/docs/MODEL_CARD.md)
for full attribution requirements.
"""


def generate_model_card(
    export_dir: Path,
    model_name: str,
    output: Path,
) -> Path:
    """Analyze an export directory and write a model card Markdown file."""
    export_dir = export_dir.resolve()
    analysis = analyze_export(export_dir)
    content = render_model_card(
        model_name=model_name,
        export_dir=export_dir,
        analysis=analysis,
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output


def cmd_generate(args: argparse.Namespace) -> int:
    try:
        path = generate_model_card(args.export_dir, args.model_name, args.output)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Wrote model card to {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="starscream-model-card",
        description="Generate model cards for ML models trained on Starscream exports",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Generate MODEL_CARD.md from an export directory")
    generate.add_argument(
        "--export-dir",
        type=Path,
        required=True,
        help="Exported dataset directory containing export_meta.json",
    )
    generate.add_argument(
        "--model-name",
        required=True,
        help="Name of the trained model (used in citations)",
    )
    generate.add_argument(
        "--output",
        type=Path,
        default=Path("MODEL_CARD.md"),
        help="Output Markdown path (default: MODEL_CARD.md)",
    )
    generate.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
