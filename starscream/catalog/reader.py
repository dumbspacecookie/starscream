"""Load and query Starscream catalog JSONL (pointer-only metadata)."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

_SEARCH_FIELDS = (
    "title",
    "description",
    "source_object",
    "source_action",
    "taxonomy_code",
    "location_name",
    "country_code",
    "source_slug",
)


def find_catalog_path(explicit: Path | str | None = None) -> Path:
    """Resolve catalog JSONL: explicit arg, env, cwd, then repo layout."""
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"Catalog not found: {path}")
        return path

    env = os.environ.get("STARSCREAM_CATALOG_PATH")
    if env:
        path = Path(env)
        if not path.is_file():
            raise FileNotFoundError(f"STARSCREAM_CATALOG_PATH not found: {path}")
        return path

    candidates = [
        Path.cwd() / "corpus" / "dataset.jsonl",
        Path.cwd() / "dataset.jsonl",
    ]
    # Editable install: starscream/catalog/reader.py → repo root
    module_root = Path(__file__).resolve().parents[2]
    candidates.append(module_root / "corpus" / "dataset.jsonl")

    for path in candidates:
        if path.is_file():
            return path

    raise FileNotFoundError(
        "Catalog JSONL not found. Clone the repo or set STARSCREAM_CATALOG_PATH "
        "to corpus/dataset.jsonl"
    )


def _normalize_license(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


def _haystack(row: dict) -> str:
    parts = [str(row.get(f) or "") for f in _SEARCH_FIELDS]
    tags = row.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    return " ".join(parts).lower()


class Catalog:
    def __init__(self, rows: list[dict], *, path: Path):
        self.path = path
        self._rows = rows
        self._by_id = {r["id"]: r for r in rows if r.get("id")}

    @classmethod
    def load(cls, path: Path | str | None = None) -> Catalog:
        catalog_path = find_catalog_path(path)
        rows: list[dict] = []
        for line in catalog_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return cls(rows, path=catalog_path)

    def __len__(self) -> int:
        return len(self._rows)

    def get(self, recording_id: str) -> dict | None:
        return self._by_id.get(recording_id)

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        source_slug: str | None = None,
        license: str | None = None,
        taxonomy_code: str | None = None,
        redistributable_only: bool = False,
    ) -> list[dict]:
        tokens = [t for t in re.split(r"\s+", query.strip().lower()) if t]
        results: list[tuple[int, dict]] = []

        for row in self._rows:
            if source_slug and row.get("source_slug") != source_slug:
                continue
            if license and _normalize_license(row.get("license")) != _normalize_license(license):
                continue
            if taxonomy_code and row.get("taxonomy_code") != taxonomy_code:
                continue
            if redistributable_only:
                lic = _normalize_license(row.get("license"))
                if lic not in {"cc0", "cc-by", "public-domain"}:
                    continue

            if not tokens:
                results.append((0, row))
                continue

            text = _haystack(row)
            score = sum(1 for t in tokens if t in text)
            if score:
                results.append((score, row))

        results.sort(key=lambda x: (-x[0], x[1].get("title") or ""))
        return [row for _, row in results[:limit]]

    def stats(self) -> dict:
        by_source: Counter[str] = Counter()
        by_license: Counter[str] = Counter()
        by_taxonomy: Counter[str] = Counter()
        grounded = 0
        with_url = 0

        for row in self._rows:
            by_source[row.get("source_slug") or "unknown"] += 1
            by_license[str(row.get("license") or "unknown")] += 1
            by_taxonomy[row.get("taxonomy_code") or "unknown"] += 1
            if row.get("source_object") and row.get("source_action"):
                grounded += 1
            if row.get("external_url"):
                with_url += 1

        total = len(self._rows)
        return {
            "catalog_path": str(self.path),
            "total": total,
            "grounded_pct": round(100.0 * grounded / total, 1) if total else 0.0,
            "with_external_url": with_url,
            "by_source": dict(by_source.most_common()),
            "by_license": dict(by_license.most_common()),
            "top_taxonomy": dict(by_taxonomy.most_common(12)),
        }

    def compact(self, row: dict) -> dict:
        """Compact subset of a row for CLI and MCP output."""
        wm = row.get("world_model_labels") or {}
        return {
            "id": row.get("id"),
            "title": row.get("title"),
            "source_object": row.get("source_object"),
            "source_action": row.get("source_action"),
            "taxonomy_code": row.get("taxonomy_code"),
            "license": row.get("license"),
            "external_url": row.get("external_url"),
            "source_slug": row.get("source_slug"),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "location_name": row.get("location_name"),
            "has_audio": row.get("has_audio"),
            "wm_object_category": wm.get("object_category") or row.get("wm_object_category"),
            "wm_interaction_type": wm.get("interaction_type") or row.get("wm_interaction_type"),
            "tags": (row.get("tags") or [])[:10],
        }
