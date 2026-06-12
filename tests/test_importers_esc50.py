"""ESC-50 importer tests — no Docker."""

import csv
from pathlib import Path

from starscream.importers.esc50 import load_esc50_csv


def test_load_esc50_csv(tmp_path: Path):
    csv_path = tmp_path / "esc50.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "category", "fold"])
        writer.writeheader()
        writer.writerow({"filename": "1-100032-A-0.wav", "category": "dog", "fold": "1"})

    records = load_esc50_csv(csv_path, copy_audio=False)
    assert len(records) == 1
    assert records[0].license == "CC-BY-NC"
    assert records[0].source_object == "domestic dog"
    assert records[0].source_action == "barking"
    assert records[0].external_id == "esc50-1-100032-A-0.wav"
