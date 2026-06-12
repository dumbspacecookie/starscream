# Storage mirrors and BitTorrent export

Starscream stores FLAC originals and spectrograms in a primary S3-compatible bucket (MinIO locally; production targets geo-distributed object storage). Phase 5 adds optional **secondary mirrors** and **BitTorrent snapshots** for bulk distribution.

## Primary object store

Configure via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `S3_ENDPOINT` | `http://localhost:9000` | Primary S3 API endpoint |
| `S3_ACCESS_KEY` | `starscream` | Access key |
| `S3_SECRET_KEY` | `starscream` | Secret key |
| `S3_BUCKET` | `starscream-audio` | Bucket name |
| `S3_REGION` | `us-east-1` | Region (required by some SDKs) |

Python API: `starscream.storage` (`put_audio`, `get_object_bytes`, `put_spectrogram`, …).

## Secondary mirrors (R2 / B2 / Wasabi)

Optional replicas copy objects from the primary bucket to additional S3-compatible endpoints.

Set `MIRROR_ENDPOINTS` to a JSON array:

```bash
MIRROR_ENDPOINTS='[
  {
    "name": "r2",
    "endpoint": "https://<account>.r2.cloudflarestorage.com",
    "access_key": "...",
    "secret_key": "...",
    "bucket": "starscream-audio",
    "region": "auto"
  },
  {
    "name": "b2",
    "endpoint": "https://s3.us-west-004.backblazeb2.com",
    "access_key": "...",
    "secret_key": "...",
    "bucket": "starscream-audio"
  },
  {
    "name": "wasabi",
    "endpoint": "https://s3.wasabisys.com",
    "access_key": "...",
    "secret_key": "...",
    "bucket": "starscream-audio",
    "region": "us-east-1"
  }
]'
```

Each entry requires `name`, `endpoint`, `access_key`, and `secret_key`. `bucket` and `region` default to the primary `S3_BUCKET` / `S3_REGION`.

### Replicate an object

```python
from starscream.storage import replicate_object

results = replicate_object("audio/abc123.flac", content_type="audio/flac")
# {"primary": True, "r2": True, "b2": True, ...}
```

If no mirrors are configured, replication is a no-op and returns `{"primary": True, "mirrors": 0}`.

## BitTorrent export snapshots

After exporting a dataset (`starscream-export run`), create a torrent or manifest for peer distribution:

```bash
starscream-export torrent ./dataset/
starscream-export torrent ./dataset/ --output ./dataset/june-2026.torrent
starscream-export torrent ./dataset/ --tracker udp://tracker.opentrackr.org:1337/announce
```

### With libtorrent (recommended)

Install optional dependency:

```bash
pip install libtorrent
```

Creates a real `.torrent` file plus `torrent_manifest.json` (file list with SHA-256).

### Without libtorrent (fallback)

Writes:

- `torrent_manifest.json` — recursive file list, sizes, SHA-256 hashes
- `magnet.txt` — magnet URI derived from a manifest-based info hash

Install libtorrent on seed boxes for standards-compliant torrents and piece hashing.

## Architecture notes

- Mirrors are **push replicas**: `replicate_object` reads from primary and `put_object` to each mirror.
- BitTorrent snapshots target **export directories** (curated ML dumps), not the live bucket.
- Organizations mirroring large corpora should run public seeds (see `starscream-spec.md` reciprocity policy).
