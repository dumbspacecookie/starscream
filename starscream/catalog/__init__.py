"""Offline catalog reader — search JSONL without Docker or a server."""

from starscream.catalog.reader import Catalog, find_catalog_path

__all__ = ["Catalog", "find_catalog_path"]
