"""Verify harvest profile config is valid JSON with expected keys."""

import json
from pathlib import Path

PROFILES = Path(__file__).resolve().parent.parent / "config" / "harvest_profiles.json"


def test_harvest_profiles_load():
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    assert "metadata_light" in data
    assert data["metadata_light"]["download"] is False
    assert "freesound" in data["freesound_metadata"]["sources"]


def test_run_harvest_profile_list():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/run_harvest_profile.py", "--list"],
        cwd=PROFILES.parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "metadata_light" in result.stdout
