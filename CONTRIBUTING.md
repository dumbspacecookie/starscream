# Contributing to Starscream

## Contributing sounds

See **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** for the full guide on recording and uploading grounded sounds.

Quick start:

```bash
pip install -e .
starscream-contrib init my-recording/
# edit manifest.json, add raw WAV/FLAC
starscream-contrib validate my-recording/manifest.json
starscream-contrib upload my-recording/manifest.json
```

## Contributing code

- Match existing code style (`ruff format . && ruff check .`)
- Add tests for new behavior
- Keep the contribution manifest schema backward-compatible when possible

Metadata schema reference: [docs/METADATA_SCHEMA.md](docs/METADATA_SCHEMA.md)

Maintainer: **dumbspacecookie** — https://github.com/dumbspacecookie/starscream
