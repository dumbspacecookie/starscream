"""Publish a Starscream export directory to Hugging Face Hub."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def publish_dataset(
    export_dir: Path,
    repo_id: str,
    token: str | None = None,
    *,
    private: bool = False,
) -> str:
    """Upload parquet/jsonl, audio/, and README.md to a Hugging Face dataset repo.

    Returns the repo URL.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise ImportError(
            "Install export extras: pip install -e '.[export]'"
        ) from exc

    export_dir = export_dir.resolve()
    if not export_dir.is_dir():
        raise FileNotFoundError(f"Export directory not found: {export_dir}")

    readme = export_dir / "README.md"
    if not readme.exists():
        raise FileNotFoundError(
            f"README.md missing in {export_dir} — run starscream-export run first"
        )

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)

    for path in sorted(export_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(export_dir).as_posix()
        logger.info("Uploading %s → %s", rel, repo_id)
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=rel,
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
        )

    return f"https://huggingface.co/datasets/{repo_id}"
