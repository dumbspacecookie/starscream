"""Create BitTorrent snapshots of export directories."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import libtorrent as lt

    HAS_LIBTORRENT = True
except ImportError:
    HAS_LIBTORRENT = False


@dataclass
class TorrentResult:
    export_dir: Path
    torrent_path: Path | None
    magnet_uri: str | None
    manifest_path: Path
    file_count: int
    total_bytes: int
    used_libtorrent: bool


_SKIP_NAMES = frozenset({"torrent_manifest.json", "magnet.txt"})


def _iter_files(root: Path) -> list[tuple[Path, str, int]]:
    files: list[tuple[Path, str, int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.name in _SKIP_NAMES or path.suffix == ".torrent":
            continue
        files.append((path, rel, path.stat().st_size))
    return files


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_manifest(export_dir: Path, files: list[tuple[Path, str, int]]) -> dict:
    entries = []
    total = 0
    for path, rel, size in files:
        total += size
        entries.append(
            {
                "path": rel,
                "size": size,
                "sha256": _sha256_file(path),
            }
        )
    return {
        "name": export_dir.name,
        "root": str(export_dir.resolve()),
        "file_count": len(entries),
        "total_bytes": total,
        "files": entries,
    }


def _bencode_bytes(data: bytes) -> bytes:
    return b"bytes:" + str(len(data)).encode() + b":" + data


def _bencode_str(text: str) -> bytes:
    encoded = text.encode()
    return str(len(encoded)).encode() + b":" + encoded


def _bencode_int(value: int) -> bytes:
    return b"i" + str(value).encode() + b"e"


def _bencode_list(items: list) -> bytes:
    return b"l" + b"".join(_bencode(item) for item in items) + b"e"


def _bencode_dict(data: dict) -> bytes:
    parts = []
    for key in sorted(data.keys()):
        parts.append(_bencode_str(key))
        parts.append(_bencode(data[key]))
    return b"d" + b"".join(parts) + b"e"


def _bencode(value) -> bytes:
    if isinstance(value, bytes):
        return _bencode_bytes(value)
    if isinstance(value, str):
        return _bencode_str(value)
    if isinstance(value, int):
        return _bencode_int(value)
    if isinstance(value, list):
        return _bencode_list(value)
    if isinstance(value, dict):
        return _bencode_dict(value)
    raise TypeError(f"unsupported bencode type: {type(value)!r}")


def _info_hash_from_manifest(manifest: dict) -> str:
    """Compute a BitTorrent-style info hash from the file manifest."""
    file_entries = []
    for entry in manifest["files"]:
        file_entries.append(
            {
                "length": entry["size"],
                "path": entry["path"].split("/"),
            }
        )
    info = {
        "name": manifest["name"],
        "piece length": 262144,
        "files": file_entries,
    }
    digest = hashlib.sha1(_bencode(info)).hexdigest()
    return digest


def _magnet_uri(name: str, info_hash: str, trackers: list[str] | None = None) -> str:
    parts = [f"magnet:?xt=urn:btih:{info_hash}", f"dn={name}"]
    for tracker in trackers or []:
        parts.append(f"tr={tracker}")
    return "&".join(parts)


def _create_with_libtorrent(
    export_dir: Path,
    torrent_path: Path,
    trackers: list[str],
) -> str:
    fs = lt.file_storage()
    lt.add_files(fs, str(export_dir.resolve()))

    torrent = lt.create_torrent(fs)
    torrent.set_creator("starscream-export")
    torrent.set_comment(f"Starscream export snapshot: {export_dir.name}")
    for tracker in trackers:
        torrent.add_tracker(tracker)

    lt.set_piece_hashes(torrent, str(export_dir.resolve()))
    torrent_bytes = lt.bencode(lt.generate.torrent.generate(torrent))
    torrent_path.write_bytes(torrent_bytes)

    meta = lt.torrent_info(torrent_bytes)
    magnet = lt.make_magnet_uri(meta)
    return magnet


def create_torrent(
    export_dir: Path,
    *,
    output: Path | None = None,
    trackers: list[str] | None = None,
) -> TorrentResult:
    """Build a .torrent (when libtorrent is installed) or manifest + magnet fallback."""
    export_dir = export_dir.resolve()
    if not export_dir.is_dir():
        raise FileNotFoundError(f"Export directory not found: {export_dir}")

    files = _iter_files(export_dir)
    if not files:
        raise ValueError(f"No files under export directory: {export_dir}")

    manifest = _build_manifest(export_dir, files)
    manifest_path = export_dir / "torrent_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    tracker_list = trackers or ["udp://tracker.opentrackr.org:1337/announce"]
    torrent_path: Path | None = None
    magnet_uri: str | None = None

    if HAS_LIBTORRENT:
        torrent_path = output or (export_dir / f"{export_dir.name}.torrent")
        magnet_uri = _create_with_libtorrent(export_dir, torrent_path, tracker_list)
        logger.info("Created torrent via libtorrent: %s", torrent_path)
    else:
        info_hash = _info_hash_from_manifest(manifest)
        magnet_uri = _magnet_uri(export_dir.name, info_hash, tracker_list)
        magnet_path = export_dir / "magnet.txt"
        magnet_path.write_text(magnet_uri + "\n", encoding="utf-8")
        logger.info("libtorrent unavailable; wrote manifest + magnet fallback")

    return TorrentResult(
        export_dir=export_dir,
        torrent_path=torrent_path,
        magnet_uri=magnet_uri,
        manifest_path=manifest_path,
        file_count=manifest["file_count"],
        total_bytes=manifest["total_bytes"],
        used_libtorrent=HAS_LIBTORRENT,
    )
