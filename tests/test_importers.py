"""Static dataset importer tests — no Docker, no audio I/O."""

import csv
from pathlib import Path

from starscream.importers.fsd50k import load_fsd50k_csv


def test_load_fsd50k_csv_parses_rows(tmp_path: Path):
    csv_path = tmp_path / "dev.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fname", "labels"])
        writer.writeheader()
        writer.writerow({"fname": "12345.wav", "labels": "Dog,Bark"})
        writer.writerow({"fname": "999.wav", "labels": "Rain"})

    records = load_fsd50k_csv(csv_path, copy_audio=False, limit=2)
    assert len(records) == 2
    assert records[0].external_id == "fsd50k-dev-12345.wav"
    assert records[0].taxonomy_code == "WILDLIFE.MAMMAL"
    assert "Dog" in records[0].tags
    assert records[1].taxonomy_code == "ATMOSPHERIC.RAIN"


def test_load_fsd50k_csv_attaches_local_audio(tmp_path: Path):
    csv_path = tmp_path / "dev.csv"
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "clip.wav").write_bytes(b"RIFFfake")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fname", "labels"])
        writer.writeheader()
        writer.writerow({"fname": "clip.wav", "labels": "Bird"})

    records = load_fsd50k_csv(csv_path, audio_dir=audio_dir, copy_audio=True)
    assert hasattr(records[0], "_preview_bytes")
    assert records[0]._preview_bytes == b"RIFFfake"
