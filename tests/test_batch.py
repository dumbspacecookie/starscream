import io
import json
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

from starscream.contrib.batch import discover_packages, packages_from_zip, validate_packages

TEMPLATE = Path(__file__).parent.parent / "starscream" / "contrib" / "templates" / "manifest.example.json"


def _wav_bytes() -> bytes:
    buf = io.BytesIO()
    t = np.linspace(0, 1.0, 48000, endpoint=False)
    sf.write(buf, 0.1 * np.sin(2 * np.pi * 440 * t), 48000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _setup_package(root: Path, name: str) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir()
    manifest = json.loads(TEMPLATE.read_text())
    manifest["audio_filename"] = "test.wav"
    (pkg_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pkg_dir / "test.wav").write_bytes(_wav_bytes())
    return pkg_dir


def test_discover_single_package(tmp_path):
    _setup_package(tmp_path, "pkg1")
    packages = discover_packages(tmp_path)
    assert len(packages) == 1
    assert packages[0].manifest.title


def test_discover_nested_packages(tmp_path):
    _setup_package(tmp_path, "a")
    _setup_package(tmp_path, "b")
    packages = discover_packages(tmp_path)
    assert len(packages) == 2


def test_packages_from_zip(tmp_path):
    _setup_package(tmp_path, "rec1")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for f in tmp_path.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(tmp_path))
    packages, tmp = packages_from_zip(zip_buf.getvalue())
    try:
        assert len(packages) == 1
        assert packages[0].manifest.title
    finally:
        tmp.cleanup()


def test_validate_batch_valid(tmp_path):
    _setup_package(tmp_path, "pkg1")
    packages = discover_packages(tmp_path)
    results = validate_packages(packages, strict=True)
    assert len(results) == 1
    assert results[0].report.valid


def test_split_assign():
    from starscream.export.split import assign_split

    assert assign_split("US") in ("train", "val")
    assert assign_split("US") == assign_split("US")
