import json
from pathlib import Path

import pytest

from starscream.catalog.reader import Catalog, find_catalog_path


@pytest.fixture
def sample_jsonl(tmp_path: Path) -> Path:
    rows = [
        {
            "id": "aaa",
            "title": "Robin song",
            "source_object": "American Robin",
            "source_action": "song",
            "taxonomy_code": "WILDLIFE.BIRD",
            "license": "CC-BY",
            "external_url": "https://example.com/1",
            "source_slug": "inaturalist",
            "tags": ["bird"],
            "has_audio": False,
        },
        {
            "id": "bbb",
            "title": "Rain on roof",
            "source_object": "rain",
            "source_action": "falling",
            "taxonomy_code": "ATMOSPHERIC.RAIN",
            "license": "pointer-only",
            "external_url": "https://archive.org/details/rain",
            "source_slug": "internet-archive",
            "tags": [],
            "has_audio": False,
        },
    ]
    path = tmp_path / "dataset.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_catalog_search(sample_jsonl: Path):
    cat = Catalog.load(sample_jsonl)
    hits = cat.search("robin bird", limit=5)
    assert len(hits) == 1
    assert hits[0]["id"] == "aaa"


def test_catalog_get(sample_jsonl: Path):
    cat = Catalog.load(sample_jsonl)
    assert cat.get("bbb")["source_object"] == "rain"
    assert cat.get("missing") is None


def test_catalog_stats(sample_jsonl: Path):
    cat = Catalog.load(sample_jsonl)
    stats = cat.stats()
    assert stats["total"] == 2
    assert stats["by_source"]["inaturalist"] == 1


def test_redistributable_filter(sample_jsonl: Path):
    cat = Catalog.load(sample_jsonl)
    rows = cat.search("", redistributable_only=True, limit=10)
    assert len(rows) == 1
    assert rows[0]["license"] == "CC-BY"


def test_find_catalog_path_explicit(sample_jsonl: Path):
    assert find_catalog_path(sample_jsonl) == sample_jsonl


def test_catalog_cli_search(sample_jsonl: Path, capsys):
    from starscream.catalog.cli import main

    assert main(["--catalog", str(sample_jsonl), "search", "rain", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "rain" in out.lower()
