"""Tests for storage mirrors and torrent export."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from starscream.config import Settings
from starscream.export.cli import main as export_main
from starscream.export.torrent import create_torrent
from starscream.storage.mirror import MirrorEndpoint, get_mirrors, replicate_object


def test_mirror_endpoints_json_parsing():
    raw = json.dumps(
        [
            {
                "name": "r2",
                "endpoint": "https://example.r2.cloudflarestorage.com",
                "access_key": "key",
                "secret_key": "secret",
                "bucket": "mirror-bucket",
            }
        ]
    )
    settings = Settings(mirror_endpoints=raw)
    assert len(settings.mirror_endpoints) == 1
    assert settings.mirror_endpoints[0]["name"] == "r2"


def test_get_mirrors_from_settings():
    mirrors_json = [
        {
            "name": "wasabi",
            "endpoint": "https://s3.wasabisys.com",
            "access_key": "a",
            "secret_key": "b",
        }
    ]
    with patch("starscream.storage.mirror.get_settings") as mock_settings:
        mock_settings.return_value.mirror_endpoints = mirrors_json
        mock_settings.return_value.s3_bucket = "starscream-audio"
        mock_settings.return_value.s3_region = "us-east-1"
        mirrors = get_mirrors()

    assert len(mirrors) == 1
    assert mirrors[0] == MirrorEndpoint(
        name="wasabi",
        endpoint="https://s3.wasabisys.com",
        access_key="a",
        secret_key="b",
        bucket="starscream-audio",
        region="us-east-1",
    )


def test_replicate_object_no_mirrors():
    with patch("starscream.storage.mirror.get_object_bytes", return_value=b"data"):
        with patch("starscream.storage.mirror.get_mirrors", return_value=[]):
            result = replicate_object("audio/test.flac")

    assert result == {"primary": True, "mirrors": 0}


def test_replicate_object_missing_primary():
    with patch("starscream.storage.mirror.get_object_bytes", return_value=None):
        result = replicate_object("missing.flac")

    assert result["primary"] is False
    assert "not found" in result["error"]


def test_replicate_object_to_mirrors():
    mirror = MirrorEndpoint(
        name="r2",
        endpoint="https://r2.example.com",
        access_key="k",
        secret_key="s",
        bucket="b",
    )
    mock_client = MagicMock()

    with patch("starscream.storage.mirror.get_object_bytes", return_value=b"flac-bytes"):
        with patch("starscream.storage.mirror.get_mirrors", return_value=[mirror]):
            with patch("starscream.storage.mirror._mirror_client", return_value=mock_client):
                result = replicate_object("audio/x.flac", content_type="audio/flac")

    assert result["primary"] is True
    assert result["r2"] is True
    mock_client.put_object.assert_called_once_with(
        Bucket="b",
        Key="audio/x.flac",
        Body=b"flac-bytes",
        ContentType="audio/flac",
    )


def _make_export_dir(tmp_path: Path) -> Path:
    export_dir = tmp_path / "dataset"
    export_dir.mkdir()
    (export_dir / "train.jsonl").write_text("{}\n", encoding="utf-8")
    audio = export_dir / "audio"
    audio.mkdir()
    (audio / "sample.flac").write_bytes(b"fake-flac")
    return export_dir


def test_create_torrent_fallback_manifest(tmp_path):
    export_dir = _make_export_dir(tmp_path)

    with patch("starscream.export.torrent.HAS_LIBTORRENT", False):
        result = create_torrent(export_dir)

    assert result.used_libtorrent is False
    assert result.torrent_path is None
    assert result.magnet_uri is not None
    assert result.magnet_uri.startswith("magnet:?xt=urn:btih:")
    assert result.manifest_path.exists()
    assert (export_dir / "magnet.txt").exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 2
    assert any(entry["path"] == "audio/sample.flac" for entry in manifest["files"])


def test_create_torrent_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(ValueError, match="No files"):
        create_torrent(empty)


def test_create_torrent_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError, match="Export directory not found"):
        create_torrent(tmp_path / "nope")


def test_cli_torrent_subcommand(tmp_path, capsys):
    export_dir = _make_export_dir(tmp_path)

    with patch("starscream.export.torrent.HAS_LIBTORRENT", False):
        code = export_main(["torrent", str(export_dir)])

    assert code == 0
    out = capsys.readouterr().out
    assert "Manifest:" in out
    assert "Magnet:" in out
    assert "libtorrent not installed" in out


def test_storage_package_exports():
    import starscream.storage as storage

    assert hasattr(storage, "put_audio")
    assert hasattr(storage, "replicate_object")
    assert hasattr(storage, "get_mirrors")
