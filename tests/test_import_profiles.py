"""Verify static import profile config and CLI list."""

import json
import subprocess
import sys
from pathlib import Path

PROFILES = Path(__file__).resolve().parent.parent / "config" / "import_profiles.json"
REPO = PROFILES.parent.parent


def test_import_profiles_load():
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    assert "esc50_metadata" in data
    entry = data["esc50_metadata"]["imports"][0]
    assert entry["importer"] == "esc50"
    assert "--no-audio" in entry["args"]


def test_run_import_profile_list():
    result = subprocess.run(
        [sys.executable, "scripts/run_import_profile.py", "--list"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "esc50_metadata" in result.stdout


def test_starscream_import_list():
    result = subprocess.run(
        [sys.executable, "-m", "starscream.importers.cli", "list"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "fsd50k" in result.stdout
    assert "esc50" in result.stdout
