"""MCP server — expose catalog search tools to MCP-compatible clients.

Usage:
    pip install -e ".[mcp]"
    starscream-mcp
    # or: python -m starscream.mcp.server

Set STARSCREAM_CATALOG_PATH if dataset.jsonl is not at corpus/dataset.jsonl.
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from starscream.catalog.reader import Catalog

mcp = FastMCP(
    "starscream-catalog",
    instructions=(
        "Starscream is a pointer catalog of grounded sounds worldwide. "
        "Rows link to upstream audio via external_url; respect per-row license. "
        "Most rows are metadata-only (has_audio=false)."
    ),
)

_catalog: Catalog | None = None


def _catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog.load(os.environ.get("STARSCREAM_CATALOG_PATH"))
    return _catalog


@mcp.tool()
def catalog_search(
    query: str,
    limit: int = 10,
    source: str | None = None,
    license: str | None = None,
    taxonomy: str | None = None,
) -> str:
    """Search grounded sound metadata by keyword (species, place, tags, title)."""
    rows = _catalog().search(
        query,
        limit=min(limit, 50),
        source_slug=source,
        license=license,
        taxonomy_code=taxonomy,
    )
    return json.dumps([_catalog().compact(r) for r in rows], indent=2, ensure_ascii=False)


@mcp.tool()
def catalog_get(recording_id: str) -> str:
    """Fetch one catalog entry by UUID."""
    row = _catalog().get(recording_id)
    if not row:
        return json.dumps({"error": "not_found", "id": recording_id})
    return json.dumps(_catalog().compact(row), indent=2, ensure_ascii=False)


@mcp.tool()
def catalog_stats() -> str:
    """Counts by source, license, and taxonomy for the bundled catalog."""
    return json.dumps(_catalog().stats(), indent=2)


@mcp.tool()
def catalog_list_redistributable(limit: int = 15) -> str:
    """List CC0 / CC-BY / public-domain rows (still use external_url for audio)."""
    rows = _catalog().search("", limit=min(limit, 50), redistributable_only=True)
    return json.dumps([_catalog().compact(r) for r in rows], indent=2, ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
