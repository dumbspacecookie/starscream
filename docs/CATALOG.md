# Using the catalog (no server, no Docker)

Starscream ships a **pointer catalog**: grounded metadata + `external_url` per sound.  
Audio stays at upstream archives (xeno-canto, Internet Archive, iNaturalist, …).

You do **not** need Postgres, MinIO, or a running API to use it.

## Get the data

```bash
git clone https://github.com/dumbspacecookie/starscream.git
cd starscream
```

The catalog file: **`corpus/dataset.jsonl`** (~4.5k rows, metadata only).

Or set:

```bash
export STARSCREAM_CATALOG_PATH=/path/to/dataset.jsonl
```

## Install (minimal)

```bash
pip install -e .
# MCP tools (optional):
pip install -e ".[mcp]"
```

No `[mcp]` needed for CLI-only use.

## CLI

```bash
python -m starscream.catalog path
python -m starscream.catalog stats
python -m starscream.catalog search "gray treefrog" --limit 5
python -m starscream.catalog search bird --source inaturalist --limit 10
python -m starscream.catalog get <uuid>
python -m starscream.catalog search rain --redistributable --limit 20
```

If `starscream-catalog` is on your PATH (after `pip install -e .`), you can omit `python -m starscream.catalog`.

## Python

```python
from starscream.catalog import Catalog

cat = Catalog.load()  # corpus/dataset.jsonl in repo root
for row in cat.search("chaffinch", limit=5):
    print(row["source_object"], row["external_url"], row["license"])
```

## MCP (optional)

Copy [mcp.json.example](../mcp.json.example) into your MCP client config and set `cwd` / `STARSCREAM_CATALOG_PATH`.

```bash
starscream-mcp
```

Tools exposed:

| Tool | Purpose |
|------|---------|
| `catalog_search` | Keyword search |
| `catalog_get` | One row by UUID |
| `catalog_stats` | Source/license/taxonomy counts |
| `catalog_list_redistributable` | CC0 / CC-BY / public-domain rows |

## Licenses

Every row has a `license` field. Most federated audio is **pointer-only** — follow `external_url` and obey upstream terms.  
See [REDISTRIBUTION.md](./REDISTRIBUTION.md).

## Growing the catalog (maintainers)

Harvest/export requires Docker + Postgres — see [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md).  
Consumers only need the committed JSONL.
