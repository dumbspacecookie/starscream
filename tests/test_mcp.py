import json
import tomllib
from pathlib import Path

import pytest

import starscream.mcp.server as server
from starscream.catalog.reader import Catalog


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
        {
            "id": "ccc",
            "title": "Public domain thunder",
            "source_object": "thunder",
            "source_action": "rumble",
            "taxonomy_code": "ATMOSPHERIC.THUNDER",
            "license": "public_domain",
            "external_url": "https://example.com/3",
            "source_slug": "internet-archive",
            "tags": [],
            "has_audio": False,
        },
    ]
    path = tmp_path / "dataset.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def reset_cache(sample_jsonl: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the server at the fixture catalog and reset the lazy-load cache."""
    monkeypatch.setenv("STARSCREAM_CATALOG_PATH", str(sample_jsonl))
    monkeypatch.setattr(server, "_catalog_cache", None)
    yield


def test_loader_returns_catalog_instance():
    # REQ: STARSCREAM-1016-S1/AC-1
    cat = server._catalog()
    assert isinstance(cat, Catalog)


def test_catalog_search_returns_matching_row():
    # REQ: STARSCREAM-1016-S1/AC-1
    result = server.catalog_search("robin bird")
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert any(r["id"] == "aaa" for r in parsed)


def test_catalog_get_found():
    # REQ: STARSCREAM-1016-S1/AC-2
    result = server.catalog_get("bbb")
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert parsed["id"] == "bbb"


def test_catalog_get_not_found():
    # REQ: STARSCREAM-1016-S1/AC-2
    result = server.catalog_get("missing")
    parsed = json.loads(result)
    assert parsed == {"error": "not_found", "id": "missing"}


def test_catalog_stats_total():
    # REQ: STARSCREAM-1016-S1/AC-3
    result = server.catalog_stats()
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert parsed["total"] == 3


def test_dev_optional_dependencies_include_mcp():
    # REQ: STARSCREAM-1016-S1/AC-4
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dev_deps = data["project"]["optional-dependencies"]["dev"]
    assert any(
        dep.replace(" ", "").startswith("mcp>=1.6.0") for dep in dev_deps
    ), "dev optional-dependencies must include mcp>=1.6.0 so tests/test_mcp.py is collected under CI .[dev]"


def test_catalog_list_redistributable():
    # REQ: STARSCREAM-1016-S1/AC-3
    result = server.catalog_list_redistributable()
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) >= 1
    allowed = {"cc0", "cc-by", "public-domain"}
    for row in parsed:
        normalized = (row["license"] or "").strip().lower().replace("_", "-")
        assert normalized in allowed
