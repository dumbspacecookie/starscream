import json
import subprocess
import sys
from pathlib import Path


def test_validate_export_sample_ok(tmp_path: Path):
    rows = [
        {
            "source_object": "dog",
            "source_action": "barking",
            "world_model_labels": {"object_category": "organism"},
            "has_audio": True,
            "audio": "audio/x.flac",
        },
        {
            "source_object": "rain",
            "source_action": "falling",
            "world_model_labels": {"object_category": "environment"},
            "has_audio": False,
            "external_url": "https://archive.org/details/rain",
        },
    ]
    path = tmp_path / "sample.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/validate_export_sample.py", str(path)],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout
