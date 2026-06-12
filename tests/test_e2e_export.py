"""E2E export: upload → starscream-export jsonl."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.e2e_fixtures import MANIFEST_TEMPLATE, clear_e2e_caches, make_wav_bytes, register_e2e_contributor

pytestmark = pytest.mark.integration


def test_e2e_export_jsonl(e2e_stack):
    from starscream.api.main import app

    clear_e2e_caches()
    client = TestClient(app)
    auth = register_e2e_contributor(client)

    unique = uuid.uuid4().hex[:8]
    manifest = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    manifest["title"] = f"E2E export {unique}"
    manifest["audio_filename"] = "e2e_export.wav"
    manifest["tags"] = [f"e2e_export_{unique}"]

    upload = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": json.dumps(manifest)},
        files={"audio": ("e2e_export.wav", make_wav_bytes(), "audio/wav")},
        headers=auth,
    )
    assert upload.status_code == 201, upload.text

    with tempfile.TemporaryDirectory(prefix="starscream_e2e_export_") as tmp:
        out_dir = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "starscream.export.cli",
                "run",
                str(out_dir),
                "--format",
                "jsonl",
                "--no-audio",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout

        dataset_jsonl = out_dir / "dataset.jsonl"
        assert dataset_jsonl.is_file()
        lines = [line for line in dataset_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) >= 1

        rows = [json.loads(line) for line in lines]
        uploaded_id = upload.json()["recording"]["id"]
        assert any(row["id"] == uploaded_id for row in rows)
