"""Tests for Hugging Face Hub publish (export/publish.py + CLI)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from starscream.export.cli import main as export_main
from starscream.export.publish import publish_dataset


def _make_export_dir(tmp_path: Path) -> Path:
    export_dir = tmp_path / "dataset"
    export_dir.mkdir()
    (export_dir / "README.md").write_text("# Starscream corpus\n", encoding="utf-8")
    (export_dir / "train.jsonl").write_text("{}\n", encoding="utf-8")
    (export_dir / "audio").mkdir()
    (export_dir / "audio" / "sample.flac").write_bytes(b"fake")
    return export_dir


def test_publish_dataset_uploads_files(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    mock_api = MagicMock()

    with patch("huggingface_hub.HfApi", return_value=mock_api):
        url = publish_dataset(export_dir, "user/starscream-corpus", token="tok")

    assert url == "https://huggingface.co/datasets/user/starscream-corpus"
    mock_api.create_repo.assert_called_once_with(
        repo_id="user/starscream-corpus",
        repo_type="dataset",
        private=False,
        exist_ok=True,
    )
    assert mock_api.upload_file.call_count == 3
    uploaded = {c.kwargs["path_in_repo"] for c in mock_api.upload_file.call_args_list}
    assert "README.md" in uploaded
    assert "train.jsonl" in uploaded
    assert "audio/sample.flac" in uploaded


def test_publish_dataset_private_repo(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    mock_api = MagicMock()

    with patch("huggingface_hub.HfApi", return_value=mock_api):
        publish_dataset(export_dir, "user/private-corpus", token="tok", private=True)

    mock_api.create_repo.assert_called_once_with(
        repo_id="user/private-corpus",
        repo_type="dataset",
        private=True,
        exist_ok=True,
    )


def test_publish_dataset_missing_readme(tmp_path):
    export_dir = tmp_path / "empty"
    export_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="README.md missing"):
        publish_dataset(export_dir, "user/repo")


def test_publish_dataset_missing_dir(tmp_path):
    missing = tmp_path / "nope"

    with pytest.raises(FileNotFoundError, match="Export directory not found"):
        publish_dataset(missing, "user/repo")


def test_cli_publish_subcommand(tmp_path, capsys):
    export_dir = _make_export_dir(tmp_path)

    with patch("starscream.export.cli.publish_dataset") as mock_publish:
        mock_publish.return_value = "https://huggingface.co/datasets/user/corpus"
        code = export_main(
            ["publish", str(export_dir), "--repo-id", "user/corpus", "--token", "tok"]
        )

    assert code == 0
    mock_publish.assert_called_once_with(
        export_dir,
        "user/corpus",
        token="tok",
        private=False,
    )
    assert "Published to" in capsys.readouterr().out


def test_cli_publish_uses_hf_token_env(tmp_path, monkeypatch):
    export_dir = _make_export_dir(tmp_path)
    monkeypatch.setenv("HF_TOKEN", "env-token")

    with patch("starscream.export.cli.publish_dataset") as mock_publish:
        mock_publish.return_value = "https://huggingface.co/datasets/user/corpus"
        code = export_main(["publish", str(export_dir), "--repo-id", "user/corpus"])

    assert code == 0
    mock_publish.assert_called_once_with(
        export_dir,
        "user/corpus",
        token="env-token",
        private=False,
    )
