# Starscream

An open catalog of sounds on Earth — what made the noise, where it happened, and where to listen (with license info).

Most rows are **metadata + a link** to the original recording. Starscream does not host the audio.

Maintained by **[dumbspacecookie](https://github.com/dumbspacecookie)**.

| I want to… | Start here |
|------------|------------|
| Search the catalog locally | [docs/CATALOG.md](./docs/CATALOG.md) |
| Understand licenses | [docs/REDISTRIBUTION.md](./docs/REDISTRIBUTION.md) |
| Build a training set | [docs/TRAINING_EXPORT.md](./docs/TRAINING_EXPORT.md) |
| Grow the index (Docker) | [docs/PHASE2_RUNBOOK.md](./docs/PHASE2_RUNBOOK.md) |

---

## Quick start

```bash
git clone https://github.com/dumbspacecookie/starscream.git
cd starscream
pip install -e .
```

The catalog lives in **`corpus/dataset.jsonl`** (~4.5k rows, no audio files in the repo).

```bash
python -m starscream.catalog stats
python -m starscream.catalog search "common chaffinch" --limit 5
python -m starscream.catalog get <recording-uuid>
```

### MCP (optional)

For tools that speak [Model Context Protocol](https://modelcontextprotocol.io):

```bash
pip install -e ".[mcp]"
python -m starscream.mcp.server
```

See [mcp.json.example](./mcp.json.example) for a sample config.

### Python

```python
from starscream.catalog import Catalog

cat = Catalog.load()
for row in cat.search("treefrog", limit=5):
    print(row["source_object"], row["external_url"], row["license"])
```

---

## Sources in the catalog

| Source | What you get |
|--------|----------------|
| iNaturalist | Species sounds with location |
| Internet Archive | Field recordings, ambient, some podcasts |
| NOAA / NASA | Public-domain space and ocean pointers |
| Xeno-canto | Wildlife (harvest locally with your own API key) |

Full list: [config/external_sound_repos.json](./config/external_sound_repos.json)

---

## Growing the catalog (optional)

Requires Docker and Postgres. Not needed if you only read `corpus/dataset.jsonl`.

```bash
docker compose up -d
cp .env.example .env
alembic upgrade head
python -m starscream.seed
python scripts/run_harvest_profile.py raw_world_full
python -m starscream.export.cli run corpus --format jsonl
```

Never commit `.env` or API keys. Details: [PHASE2_RUNBOOK.md](./docs/PHASE2_RUNBOOK.md).

---

## Layout

```
corpus/dataset.jsonl     # catalog (committed)
corpus/catalog_audit.json
starscream/catalog/      # offline search
starscream/mcp/          # MCP server
starscream/federation/   # harvest connectors
docs/CATALOG.md
```

---

## Development

```bash
ruff check starscream tests
pytest --ignore=tests/test_e2e.py --ignore=tests/test_e2e_export.py
```

Integration tests need Docker: `STARSCREAM_E2E_COMPOSE=1 pytest tests/test_e2e.py -m integration`

## License

- Code: [MIT](./LICENSE) — Copyright dumbspacecookie
- Catalog rows: per-row `license` in JSONL — [DATA_LICENSE.md](./docs/DATA_LICENSE.md)
